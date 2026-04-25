/**
 * List Available Gemini Models
 */
import { GoogleGenerativeAI } from '@google/generative-ai';

const apiKey = process.env.GEMINI_API_KEY || '';

if (!apiKey) {
  console.error('❌ GEMINI_API_KEY environment variable required');
  process.exit(1);
}

const genAI = new GoogleGenerativeAI(apiKey);

async function listModels() {
  try {
    console.log('🔍 Fetching available models...\n');

    // Try to list models
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    const data = await response.json();

    console.log('✅ Available Models:\n');

    if (data.models && data.models.length > 0) {
      data.models.forEach((model: any) => {
        console.log(`📦 ${model.name}`);
        console.log(`   Display Name: ${model.displayName}`);
        console.log(`   Description: ${model.description}`);
        console.log(`   Supported Methods: ${model.supportedGenerationMethods?.join(', ')}`);
        console.log(`   Vision Capable: ${model.supportedGenerationMethods?.includes('generateContent')}`);
        console.log('');
      });
    } else {
      console.log('⚠️  No models found or API key has no access');
    }

  } catch (error: any) {
    console.error('❌ Error:', error.message);
  }
}

listModels();
