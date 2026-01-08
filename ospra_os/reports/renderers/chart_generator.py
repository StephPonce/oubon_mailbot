"""
Chart Generator for Business Reports

Uses matplotlib to generate professional charts:
- Line charts (revenue trends, profit trends)
- Bar charts (product performance, ad performance)
- Pie charts (cost breakdown, revenue by category)
- Customizable colors and branding
"""
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server-side generation

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
import io
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Generate charts for business reports"""

    def __init__(self, branding: Optional[Dict] = None):
        """
        Initialize chart generator with branding

        Args:
            branding: Branding config with primary_color, secondary_color
        """
        self.branding = branding or self._get_default_branding()

        # Set default style
        plt.style.use('seaborn-v0_8-darkgrid')

        # Color palette based on branding
        self.primary_color = self.branding.get('primary_color', '#3b82f6')
        self.secondary_color = self.branding.get('secondary_color', '#10b981')
        self.color_palette = [
            self.primary_color,
            self.secondary_color,
            '#f59e0b',  # amber
            '#ef4444',  # red
            '#8b5cf6',  # purple
            '#ec4899',  # pink
        ]

    # ==================== Line Charts ====================

    def generate_revenue_trend(
        self,
        dates: List[str],
        revenue: List[float],
        width: int = 800,
        height: int = 400
    ) -> io.BytesIO:
        """
        Generate revenue trend line chart

        Args:
            dates: List of date labels
            revenue: List of revenue values
            width: Chart width in pixels
            height: Chart height in pixels

        Returns:
            Chart as BytesIO buffer
        """
        logger.info("[TREND] Generating revenue trend chart")

        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)

        # Plot line
        ax.plot(
            dates,
            revenue,
            color=self.primary_color,
            linewidth=2.5,
            marker='o',
            markersize=6,
            markerfacecolor=self.secondary_color,
            markeredgecolor='white',
            markeredgewidth=2
        )

        # Styling
        ax.set_title('Revenue Trend', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Revenue ($)', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--')

        # Format y-axis as currency
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # Rotate x-axis labels for readability
        plt.xticks(rotation=45, ha='right')

        # Tight layout
        plt.tight_layout()

        # Save to buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        return buffer

    def generate_metric_comparison(
        self,
        labels: List[str],
        current: List[float],
        previous: List[float],
        metric_name: str = 'Metric',
        width: int = 800,
        height: int = 400
    ) -> io.BytesIO:
        """
        Generate comparison line chart (current vs previous period)

        Args:
            labels: X-axis labels (dates, categories)
            current: Current period values
            previous: Previous period values
            metric_name: Name of the metric
            width: Chart width
            height: Chart height

        Returns:
            Chart as BytesIO buffer
        """
        logger.info(f"[STATS] Generating {metric_name} comparison chart")

        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)

        # Plot both lines
        ax.plot(
            labels,
            current,
            color=self.primary_color,
            linewidth=2.5,
            marker='o',
            markersize=6,
            label='Current Period'
        )

        ax.plot(
            labels,
            previous,
            color=self.secondary_color,
            linewidth=2.5,
            marker='s',
            markersize=6,
            linestyle='--',
            label='Previous Period'
        )

        # Styling
        ax.set_title(f'{metric_name} Comparison', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel(metric_name, fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best', framealpha=0.9)

        # Rotate x-axis labels
        plt.xticks(rotation=45, ha='right')

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== Bar Charts ====================

    def generate_product_performance(
        self,
        product_names: List[str],
        revenue: List[float],
        top_n: int = 10,
        width: int = 800,
        height: int = 500
    ) -> io.BytesIO:
        """
        Generate product performance bar chart

        Args:
            product_names: Product names
            revenue: Revenue per product
            top_n: Number of top products to show
            width: Chart width
            height: Chart height

        Returns:
            Chart as BytesIO buffer
        """
        logger.info("[PACKAGE] Generating product performance chart")

        # Sort and take top N
        sorted_data = sorted(
            zip(product_names, revenue),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        names, values = zip(*sorted_data) if sorted_data else ([], [])

        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)

        # Create horizontal bar chart
        bars = ax.barh(
            range(len(names)),
            values,
            color=self.primary_color,
            edgecolor='white',
            linewidth=1.5
        )

        # Add value labels
        for i, (bar, value) in enumerate(zip(bars, values)):
            ax.text(
                value,
                i,
                f' ${value:,.0f}',
                va='center',
                fontsize=10,
                fontweight='bold'
            )

        # Styling
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=10)
        ax.set_xlabel('Revenue ($)', fontsize=12)
        ax.set_title(f'Top {top_n} Products by Revenue', fontsize=16, fontweight='bold', pad=20)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:,.0f}'))
        ax.grid(True, axis='x', alpha=0.3, linestyle='--')

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        return buffer

    def generate_grouped_bar_chart(
        self,
        categories: List[str],
        data_groups: Dict[str, List[float]],
        title: str = 'Comparison',
        ylabel: str = 'Value',
        width: int = 800,
        height: int = 400
    ) -> io.BytesIO:
        """
        Generate grouped bar chart (multiple series)

        Args:
            categories: X-axis categories
            data_groups: Dict of {series_name: [values]}
            title: Chart title
            ylabel: Y-axis label
            width: Chart width
            height: Chart height

        Returns:
            Chart as BytesIO buffer
        """
        logger.info(f"[STATS] Generating grouped bar chart: {title}")

        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)

        x = range(len(categories))
        bar_width = 0.8 / len(data_groups)
        colors = self.color_palette[:len(data_groups)]

        # Plot each group
        for i, (group_name, values) in enumerate(data_groups.items()):
            offset = (i - len(data_groups)/2 + 0.5) * bar_width
            ax.bar(
                [xi + offset for xi in x],
                values,
                bar_width,
                label=group_name,
                color=colors[i],
                edgecolor='white',
                linewidth=1
            )

        # Styling
        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=45, ha='right')
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== Pie Charts ====================

    def generate_cost_breakdown(
        self,
        categories: List[str],
        amounts: List[float],
        width: int = 600,
        height: int = 600
    ) -> io.BytesIO:
        """
        Generate cost breakdown pie chart

        Args:
            categories: Cost categories
            amounts: Amount per category
            width: Chart width
            height: Chart height

        Returns:
            Chart as BytesIO buffer
        """
        logger.info("[PRICE] Generating cost breakdown pie chart")

        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)

        # Filter out zero values
        filtered = [(cat, amt) for cat, amt in zip(categories, amounts) if amt > 0]
        if not filtered:
            # Return empty chart
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=14)
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close(fig)
            return buffer

        cats, vals = zip(*filtered)

        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            vals,
            labels=cats,
            autopct='%1.1f%%',
            startangle=90,
            colors=self.color_palette[:len(cats)],
            explode=[0.05] * len(cats),  # Slight separation
            shadow=True,
            textprops={'fontsize': 10}
        )

        # Make percentage text bold and white
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(9)

        ax.set_title('Cost Breakdown', fontsize=16, fontweight='bold', pad=20)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        return buffer

    def generate_revenue_by_category(
        self,
        categories: List[str],
        revenue: List[float],
        width: int = 600,
        height: int = 600
    ) -> io.BytesIO:
        """
        Generate revenue by category pie chart

        Args:
            categories: Revenue categories
            revenue: Revenue per category
            width: Chart width
            height: Chart height

        Returns:
            Chart as BytesIO buffer
        """
        logger.info("[STATS] Generating revenue by category pie chart")

        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)

        # Filter out zero values
        filtered = [(cat, rev) for cat, rev in zip(categories, revenue) if rev > 0]
        if not filtered:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=14)
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close(fig)
            return buffer

        cats, vals = zip(*filtered)

        # Create donut chart (pie with hole in center)
        wedges, texts, autotexts = ax.pie(
            vals,
            labels=cats,
            autopct=lambda pct: f'${pct * sum(vals) / 100:,.0f}\n({pct:.1f}%)',
            startangle=90,
            colors=self.color_palette[:len(cats)],
            explode=[0.05] * len(cats),
            shadow=True,
            textprops={'fontsize': 9},
            pctdistance=0.85
        )

        # Draw center circle for donut effect
        centre_circle = plt.Circle((0, 0), 0.70, fc='white')
        ax.add_artist(centre_circle)

        # Make percentage text bold and white
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(8)

        ax.set_title('Revenue by Category', fontsize=16, fontweight='bold', pad=20)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== Multi-Chart Layouts ====================

    def generate_dashboard_overview(
        self,
        data: Dict,
        width: int = 1200,
        height: int = 800
    ) -> io.BytesIO:
        """
        Generate dashboard-style overview with multiple charts

        Args:
            data: Dict containing all necessary data for charts
            width: Overall width
            height: Overall height

        Returns:
            Combined chart as BytesIO buffer
        """
        logger.info("[STATS] Generating dashboard overview")

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(
            2, 2,
            figsize=(width/100, height/100),
            dpi=100
        )

        # Chart 1: Revenue trend (top-left)
        if 'revenue_trend' in data:
            dates = data['revenue_trend'].get('dates', [])
            revenue = data['revenue_trend'].get('values', [])
            if dates and revenue:
                ax1.plot(dates, revenue, color=self.primary_color, linewidth=2, marker='o')
                ax1.set_title('Revenue Trend', fontsize=12, fontweight='bold')
                ax1.grid(True, alpha=0.3)
                ax1.tick_params(axis='x', rotation=45)

        # Chart 2: Top products (top-right)
        if 'top_products' in data:
            products = data['top_products'].get('names', [])
            values = data['top_products'].get('revenue', [])
            if products and values:
                ax2.barh(range(len(products)), values, color=self.secondary_color)
                ax2.set_yticks(range(len(products)))
                ax2.set_yticklabels(products, fontsize=9)
                ax2.set_title('Top Products', fontsize=12, fontweight='bold')
                ax2.grid(True, axis='x', alpha=0.3)

        # Chart 3: Cost breakdown (bottom-left)
        if 'cost_breakdown' in data:
            categories = data['cost_breakdown'].get('categories', [])
            amounts = data['cost_breakdown'].get('amounts', [])
            if categories and amounts:
                ax3.pie(
                    amounts,
                    labels=categories,
                    autopct='%1.1f%%',
                    colors=self.color_palette[:len(categories)],
                    textprops={'fontsize': 8}
                )
                ax3.set_title('Cost Breakdown', fontsize=12, fontweight='bold')

        # Chart 4: ROAS by platform (bottom-right)
        if 'roas_by_platform' in data:
            platforms = data['roas_by_platform'].get('platforms', [])
            roas = data['roas_by_platform'].get('roas', [])
            if platforms and roas:
                bars = ax4.bar(range(len(platforms)), roas, color=self.color_palette[:len(platforms)])
                ax4.set_xticks(range(len(platforms)))
                ax4.set_xticklabels(platforms)
                ax4.set_title('ROAS by Platform', fontsize=12, fontweight='bold')
                ax4.set_ylabel('ROAS')
                ax4.grid(True, axis='y', alpha=0.3)

                # Add horizontal line at 1.0 (break-even)
                ax4.axhline(y=1.0, color='red', linestyle='--', linewidth=1, alpha=0.5)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        return buffer

    # ==================== Helper Methods ====================

    def _get_default_branding(self) -> Dict:
        """Get default branding configuration"""
        return {
            'primary_color': '#3b82f6',
            'secondary_color': '#10b981'
        }


# Export singleton instance creator
def create_chart_generator(branding: Optional[Dict] = None) -> ChartGenerator:
    """Create a chart generator instance with branding"""
    return ChartGenerator(branding)
