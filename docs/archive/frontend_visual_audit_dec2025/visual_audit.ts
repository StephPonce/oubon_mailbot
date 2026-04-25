/**
 * Automated Visual Audit Script
 * Takes screenshots of all pages and analyzes with Gemini Vision
 */

import puppeteer, { Browser, Page } from 'puppeteer';
import * as fs from 'fs';
import * as path from 'path';
import { GoogleGenerativeAI } from '@google/generative-ai';

// Configuration
const CONFIG = {
  baseUrl: 'http://localhost:5173',  // Your frontend dev server
  screenshotDir: './audit_screenshots',
  outputReport: './visual_audit_report.md',
  geminiApiKey: process.env.GEMINI_API_KEY || '',
  viewport: { width: 1920, height: 1080 },

  // All routes from Layout.tsx
  routes: [
    { path: '/', name: 'Command Center (Dashboard)' },
    { path: '/actions', name: 'Pending Actions' },
    { path: '/products', name: 'Product Discovery' },
    { path: '/trends', name: 'Live Trends' },
    { path: '/intelligence', name: 'Ospra Intelligence' },
    { path: '/niches', name: 'Niche Analysis' },
    { path: '/competitors', name: 'Competitors' },
    { path: '/templates', name: 'Template Vault' },
    { path: '/shopify', name: 'Shopify Store' },
    { path: '/inventory', name: 'Inventory' },
    { path: '/auto-deploy', name: 'Auto-Deployment' },
    { path: '/customers', name: 'Customer Analytics' },
    { path: '/email', name: 'Email Automation' },
    { path: '/ads', name: 'Advertising' },
    { path: '/testing', name: 'A/B Testing' },
    { path: '/health', name: 'System Health' },
    { path: '/stores', name: 'Stores Management' },
    { path: '/subscription', name: 'Subscription' },
    { path: '/settings', name: 'Settings' },
  ],
};

// Design system reference for Gemini
const DESIGN_SYSTEM = `
OSPRA DESIGN SYSTEM - Liquid Glass Aesthetic (Apple Vision Pro inspired)

COLORS:
- Background: Dark (#0a0a0f to #1a1a2e gradient)
- Glass surfaces: rgba(255,255,255,0.05) to rgba(255,255,255,0.1)
- Primary accent: Cyan/Teal (#06b6d4, #14b8a6)
- Secondary accent: Purple/Blue (#8b5cf6, #6366f1)
- Text primary: White (#ffffff)
- Text secondary: Gray (#9ca3af)
- Success: Green (#10b981)
- Warning: Amber (#f59e0b)
- Error: Red (#ef4444)

GLASSMORPHISM REQUIREMENTS:
- backdrop-filter: blur(20px) on card surfaces
- Subtle borders: 1px solid rgba(255,255,255,0.1)
- Soft shadows with color glow
- Layered depth with multiple glass panels

TYPOGRAPHY:
- Clean, modern sans-serif (Inter, SF Pro)
- Clear hierarchy: large bold headers, medium body, small labels
- High contrast for readability

COMPONENTS SHOULD HAVE:
- Smooth hover transitions
- Subtle animations
- Clear active/selected states
- Consistent border radius (rounded-xl, rounded-2xl)
- Proper spacing (not cramped, not too sparse)

OVERALL FEEL:
- Premium, futuristic, professional
- Like a high-end trading terminal meets Apple design
- "Ospra" AI should feel alive and integrated
`;

interface ScreenshotResult {
  route: string;
  name: string;
  screenshotPath: string;
  timestamp: string;
  error?: string;
}

interface AnalysisResult {
  route: string;
  name: string;
  screenshotPath: string;
  analysis: {
    overallScore: number;
    designSystemCompliance: string;
    functionalIssues: string[];
    visualIssues: string[];
    recommendations: string[];
    brokenElements: string[];
    missingElements: string[];
  };
}

class VisualAuditor {
  private browser: Browser | null = null;
  private page: Page | null = null;
  private genAI: GoogleGenerativeAI;
  private model: any;

  constructor() {
    if (!CONFIG.geminiApiKey) {
      throw new Error('GEMINI_API_KEY environment variable required');
    }
    this.genAI = new GoogleGenerativeAI(CONFIG.geminiApiKey);
    this.model = this.genAI.getGenerativeModel({ model: 'gemini-2.5-flash' });
  }

  async initialize(): Promise<void> {
    // Create screenshot directory
    if (!fs.existsSync(CONFIG.screenshotDir)) {
      fs.mkdirSync(CONFIG.screenshotDir, { recursive: true });
    }

    // Launch browser
    this.browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    this.page = await this.browser.newPage();
    await this.page.setViewport(CONFIG.viewport);

    console.log('✅ Browser initialized');
  }

  async captureScreenshots(): Promise<ScreenshotResult[]> {
    const results: ScreenshotResult[] = [];

    if (!this.page) {
      throw new Error('Browser not initialized');
    }

    for (const route of CONFIG.routes) {
      const result: ScreenshotResult = {
        route: route.path,
        name: route.name,
        screenshotPath: '',
        timestamp: new Date().toISOString()
      };

      try {
        console.log(`📸 Capturing: ${route.name} (${route.path})`);

        await this.page.goto(`${CONFIG.baseUrl}${route.path}`, {
          waitUntil: 'networkidle2',
          timeout: 30000
        });

        // Wait a bit for any animations/loading
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Take screenshot
        const filename = `${route.path.replace(/\//g, '_') || 'home'}.png`;
        const screenshotPath = path.join(CONFIG.screenshotDir, filename);

        await this.page.screenshot({
          path: screenshotPath,
          fullPage: true
        });

        result.screenshotPath = screenshotPath;
        console.log(`  ✅ Saved: ${filename}`);

      } catch (error: any) {
        result.error = error.message;
        console.log(`  ❌ Error: ${error.message}`);
      }

      results.push(result);
    }

    return results;
  }

  async analyzeScreenshot(screenshot: ScreenshotResult): Promise<AnalysisResult> {
    if (screenshot.error || !screenshot.screenshotPath) {
      return {
        route: screenshot.route,
        name: screenshot.name,
        screenshotPath: screenshot.screenshotPath,
        analysis: {
          overallScore: 0,
          designSystemCompliance: 'Unable to analyze - screenshot failed',
          functionalIssues: [screenshot.error || 'Screenshot capture failed'],
          visualIssues: [],
          recommendations: ['Fix the page so it loads correctly'],
          brokenElements: [],
          missingElements: []
        }
      };
    }

    try {
      // Read image and convert to base64
      const imageBuffer = fs.readFileSync(screenshot.screenshotPath);
      const base64Image = imageBuffer.toString('base64');

      const prompt = `
You are a senior UI/UX designer and frontend developer auditing a dashboard application.

DESIGN SYSTEM REFERENCE:
${DESIGN_SYSTEM}

PAGE BEING ANALYZED: ${screenshot.name} (${screenshot.route})

Analyze this screenshot and provide a detailed assessment in the following JSON format:

{
  "overallScore": <number 0-100>,
  "designSystemCompliance": "<brief assessment of how well it matches the liquid glass aesthetic>",
  "functionalIssues": [
    "<list any obvious functional problems: broken buttons, empty states that shouldn't be empty, missing data, error messages showing, etc.>"
  ],
  "visualIssues": [
    "<list visual/design problems: wrong colors, poor spacing, inconsistent typography, missing glassmorphism effects, etc.>"
  ],
  "recommendations": [
    "<specific actionable fixes, be detailed with CSS properties or component changes needed>"
  ],
  "brokenElements": [
    "<list any elements that appear broken, disabled, or non-functional>"
  ],
  "missingElements": [
    "<list any UI elements that should be on this page but aren't (based on the page name/purpose)>"
  ]
}

Be brutally honest. This is for improving the product. Identify EVERYTHING that's wrong.
Focus especially on:
1. Does it actually look like a premium "liquid glass" dashboard?
2. Are there obvious broken/empty states?
3. Does the page serve its stated purpose (${screenshot.name})?
4. Would a user be confused or frustrated?

Return ONLY the JSON, no other text.
`;

      const result = await this.model.generateContent([
        prompt,
        {
          inlineData: {
            mimeType: 'image/png',
            data: base64Image
          }
        }
      ]);

      const responseText = result.response.text();

      // Parse JSON from response (handle markdown code blocks)
      let jsonText = responseText;
      if (responseText.includes('```json')) {
        jsonText = responseText.split('```json')[1].split('```')[0];
      } else if (responseText.includes('```')) {
        jsonText = responseText.split('```')[1].split('```')[0];
      }

      const analysis = JSON.parse(jsonText.trim());

      return {
        route: screenshot.route,
        name: screenshot.name,
        screenshotPath: screenshot.screenshotPath,
        analysis
      };

    } catch (error: any) {
      console.error(`Analysis error for ${screenshot.name}:`, error.message);
      return {
        route: screenshot.route,
        name: screenshot.name,
        screenshotPath: screenshot.screenshotPath,
        analysis: {
          overallScore: 0,
          designSystemCompliance: 'Analysis failed',
          functionalIssues: [`Analysis error: ${error.message}`],
          visualIssues: [],
          recommendations: [],
          brokenElements: [],
          missingElements: []
        }
      };
    }
  }

  async analyzeAllScreenshots(screenshots: ScreenshotResult[]): Promise<AnalysisResult[]> {
    const results: AnalysisResult[] = [];

    for (const screenshot of screenshots) {
      console.log(`🔍 Analyzing: ${screenshot.name}`);
      const analysis = await this.analyzeScreenshot(screenshot);
      results.push(analysis);

      // Rate limiting - Gemini has limits
      await new Promise(resolve => setTimeout(resolve, 3000));
    }

    return results;
  }

  generateReport(results: AnalysisResult[]): string {
    const timestamp = new Date().toISOString();

    // Calculate overall stats
    const totalScore = results.reduce((sum, r) => sum + r.analysis.overallScore, 0);
    const avgScore = Math.round(totalScore / results.length);

    const allFunctionalIssues = results.flatMap(r => r.analysis.functionalIssues);
    const allVisualIssues = results.flatMap(r => r.analysis.visualIssues);
    const allBrokenElements = results.flatMap(r => r.analysis.brokenElements);

    let report = `# Ospra Frontend Visual Audit Report

Generated: ${timestamp}

## Executive Summary

| Metric | Value |
|--------|-------|
| Pages Audited | ${results.length} |
| Average Score | ${avgScore}/100 |
| Total Functional Issues | ${allFunctionalIssues.length} |
| Total Visual Issues | ${allVisualIssues.length} |
| Broken Elements Found | ${allBrokenElements.length} |

### Overall Assessment

${avgScore >= 80 ? '✅ Good' : avgScore >= 60 ? '⚠️ Needs Work' : '❌ Critical Issues'}

---

## Page-by-Page Analysis

`;

    // Sort by score (worst first)
    const sortedResults = [...results].sort((a, b) => a.analysis.overallScore - b.analysis.overallScore);

    for (const result of sortedResults) {
      const scoreEmoji = result.analysis.overallScore >= 80 ? '✅' :
                        result.analysis.overallScore >= 60 ? '⚠️' : '❌';

      report += `### ${scoreEmoji} ${result.name} (${result.route})

**Score: ${result.analysis.overallScore}/100**

**Design Compliance:** ${result.analysis.designSystemCompliance}

`;

      if (result.analysis.functionalIssues.length > 0) {
        report += `**Functional Issues:**
${result.analysis.functionalIssues.map(i => `- ❌ ${i}`).join('\n')}

`;
      }

      if (result.analysis.visualIssues.length > 0) {
        report += `**Visual Issues:**
${result.analysis.visualIssues.map(i => `- 🎨 ${i}`).join('\n')}

`;
      }

      if (result.analysis.brokenElements.length > 0) {
        report += `**Broken Elements:**
${result.analysis.brokenElements.map(i => `- 🔴 ${i}`).join('\n')}

`;
      }

      if (result.analysis.missingElements.length > 0) {
        report += `**Missing Elements:**
${result.analysis.missingElements.map(i => `- ⚪ ${i}`).join('\n')}

`;
      }

      if (result.analysis.recommendations.length > 0) {
        report += `**Recommendations:**
${result.analysis.recommendations.map(i => `- 💡 ${i}`).join('\n')}

`;
      }

      report += `---

`;
    }

    // Priority fix list
    report += `## Priority Fix List

### 🔴 Critical (Fix Immediately)
${sortedResults
  .filter(r => r.analysis.overallScore < 50)
  .map(r => `- **${r.name}** (Score: ${r.analysis.overallScore}) - ${r.analysis.functionalIssues[0] || 'Multiple issues'}`)
  .join('\n') || 'None'}

### 🟠 High Priority
${sortedResults
  .filter(r => r.analysis.overallScore >= 50 && r.analysis.overallScore < 70)
  .map(r => `- **${r.name}** (Score: ${r.analysis.overallScore})`)
  .join('\n') || 'None'}

### 🟡 Medium Priority
${sortedResults
  .filter(r => r.analysis.overallScore >= 70 && r.analysis.overallScore < 85)
  .map(r => `- **${r.name}** (Score: ${r.analysis.overallScore})`)
  .join('\n') || 'None'}

### 🟢 Low Priority (Polish)
${sortedResults
  .filter(r => r.analysis.overallScore >= 85)
  .map(r => `- **${r.name}** (Score: ${r.analysis.overallScore})`)
  .join('\n') || 'None'}

---

## All Broken Elements (Aggregated)

${[...new Set(allBrokenElements)].map(e => `- ${e}`).join('\n') || 'None found'}

## All Functional Issues (Aggregated)

${[...new Set(allFunctionalIssues)].map(e => `- ${e}`).join('\n') || 'None found'}
`;

    return report;
  }

  async cleanup(): Promise<void> {
    if (this.browser) {
      await this.browser.close();
    }
  }

  async run(): Promise<void> {
    try {
      console.log('🚀 Starting Visual Audit...\n');

      await this.initialize();

      console.log('\n📸 Phase 1: Capturing Screenshots...\n');
      const screenshots = await this.captureScreenshots();

      console.log('\n🔍 Phase 2: Analyzing with Gemini Vision...\n');
      const analyses = await this.analyzeAllScreenshots(screenshots);

      console.log('\n📝 Phase 3: Generating Report...\n');
      const report = this.generateReport(analyses);

      // Save report
      fs.writeFileSync(CONFIG.outputReport, report);
      console.log(`✅ Report saved to: ${CONFIG.outputReport}`);

      // Save raw JSON data
      fs.writeFileSync(
        './visual_audit_data.json',
        JSON.stringify(analyses, null, 2)
      );
      console.log('✅ Raw data saved to: visual_audit_data.json');

      // Print summary
      const avgScore = Math.round(
        analyses.reduce((sum, r) => sum + r.analysis.overallScore, 0) / analyses.length
      );

      console.log('\n========================================');
      console.log('         VISUAL AUDIT COMPLETE          ');
      console.log('========================================');
      console.log(`Average Score: ${avgScore}/100`);
      console.log(`Pages Audited: ${analyses.length}`);
      console.log(`Report: ${CONFIG.outputReport}`);
      console.log('========================================\n');

    } catch (error) {
      console.error('Audit failed:', error);
    } finally {
      await this.cleanup();
    }
  }
}

// Run the audit
const auditor = new VisualAuditor();
auditor.run();
