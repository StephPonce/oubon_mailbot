"""
Statistical Analysis for A/B Testing

Calculates statistical significance, confidence intervals, and p-values
for conversion rate comparisons.
"""

import math
from typing import Dict, Any, Tuple


class StatisticalCalculator:
    """
    Statistical significance calculator for A/B tests

    Uses z-test for proportions to determine if variant performance
    differs significantly from control.
    """

    @staticmethod
    def calculate_conversion_rate(conversions: int, impressions: int) -> float:
        """Calculate conversion rate as percentage"""
        if impressions == 0:
            return 0.0
        return (conversions / impressions) * 100

    @staticmethod
    def calculate_standard_error(
        conversions: int,
        impressions: int
    ) -> float:
        """
        Calculate standard error for conversion rate

        SE = sqrt(p * (1 - p) / n)
        where p = conversion rate, n = sample size
        """
        if impressions == 0:
            return 0.0

        p = conversions / impressions
        se = math.sqrt((p * (1 - p)) / impressions)
        return se

    @staticmethod
    def calculate_pooled_standard_error(
        control_conversions: int,
        control_impressions: int,
        variant_conversions: int,
        variant_impressions: int
    ) -> float:
        """
        Calculate pooled standard error for two-proportion z-test

        SE_pooled = sqrt(p_pooled * (1 - p_pooled) * (1/n1 + 1/n2))
        where p_pooled = (x1 + x2) / (n1 + n2)
        """
        if control_impressions == 0 or variant_impressions == 0:
            return 0.0

        # Pooled conversion rate
        total_conversions = control_conversions + variant_conversions
        total_impressions = control_impressions + variant_impressions
        p_pooled = total_conversions / total_impressions

        # Pooled standard error
        se = math.sqrt(
            p_pooled * (1 - p_pooled) * (
                (1 / control_impressions) + (1 / variant_impressions)
            )
        )

        return se

    @staticmethod
    def calculate_z_score(
        control_conversions: int,
        control_impressions: int,
        variant_conversions: int,
        variant_impressions: int
    ) -> float:
        """
        Calculate z-score for two-proportion test

        z = (p1 - p2) / SE_pooled
        """
        if control_impressions == 0 or variant_impressions == 0:
            return 0.0

        # Conversion rates
        p1 = control_conversions / control_impressions
        p2 = variant_conversions / variant_impressions

        # Pooled standard error
        se = StatisticalCalculator.calculate_pooled_standard_error(
            control_conversions,
            control_impressions,
            variant_conversions,
            variant_impressions
        )

        if se == 0:
            return 0.0

        # Z-score
        z = (p2 - p1) / se
        return z

    @staticmethod
    def z_to_p_value(z_score: float, two_tailed: bool = True) -> float:
        """
        Convert z-score to p-value using normal distribution approximation

        Uses the error function (erf) approximation for CDF of standard normal.
        """
        # Cumulative distribution function for standard normal
        # CDF(z) ≈ 0.5 * (1 + erf(z / sqrt(2)))

        # For simplicity, using a lookup table approximation
        abs_z = abs(z_score)

        # Common z-scores and their one-tailed p-values
        z_table = {
            0.0: 0.5000,
            0.5: 0.3085,
            1.0: 0.1587,
            1.28: 0.1003,
            1.5: 0.0668,
            1.645: 0.0500,
            1.96: 0.0250,
            2.0: 0.0228,
            2.33: 0.0099,
            2.5: 0.0062,
            2.58: 0.0049,
            3.0: 0.0013,
            3.5: 0.0002,
            4.0: 0.00003
        }

        # Find closest z-score in table
        p_value = 0.0
        for z_val, p_val in sorted(z_table.items()):
            if abs_z <= z_val:
                p_value = p_val
                break
        else:
            # If z-score is very large, p-value is very small
            p_value = 0.00001

        # Two-tailed test doubles the p-value
        if two_tailed:
            p_value *= 2

        return p_value

    @staticmethod
    def get_z_critical(confidence_level: float, two_tailed: bool = True) -> float:
        """
        Get critical z-score for given confidence level

        Common values:
        - 90% confidence → z = 1.645 (two-tailed)
        - 95% confidence → z = 1.96 (two-tailed)
        - 99% confidence → z = 2.58 (two-tailed)
        """
        # Lookup table for common confidence levels
        z_critical_table = {
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.58,
            0.999: 3.29
        }

        # Find closest confidence level
        z_critical = z_critical_table.get(confidence_level, 1.96)

        if not two_tailed:
            # One-tailed test has different critical values
            one_tailed_table = {
                0.90: 1.28,
                0.95: 1.645,
                0.99: 2.33,
                0.999: 3.09
            }
            z_critical = one_tailed_table.get(confidence_level, 1.645)

        return z_critical

    @staticmethod
    def calculate_confidence_interval(
        conversions: int,
        impressions: int,
        confidence_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for conversion rate

        CI = p ± z_critical * SE
        """
        if impressions == 0:
            return (0.0, 0.0)

        p = conversions / impressions
        se = StatisticalCalculator.calculate_standard_error(conversions, impressions)
        z_critical = StatisticalCalculator.get_z_critical(confidence_level, two_tailed=True)

        margin_of_error = z_critical * se

        lower = max(0.0, p - margin_of_error)  # Can't be negative
        upper = min(1.0, p + margin_of_error)  # Can't exceed 100%

        return (lower * 100, upper * 100)  # Return as percentages

    @staticmethod
    def calculate_relative_lift(
        control_conversions: int,
        control_impressions: int,
        variant_conversions: int,
        variant_impressions: int
    ) -> float:
        """
        Calculate relative lift of variant vs control

        Lift = ((variant_rate - control_rate) / control_rate) * 100
        """
        if control_impressions == 0 or control_conversions == 0:
            return 0.0

        control_rate = control_conversions / control_impressions
        variant_rate = variant_conversions / variant_impressions if variant_impressions > 0 else 0

        lift = ((variant_rate - control_rate) / control_rate) * 100
        return lift

    @staticmethod
    def calculate_sample_size_needed(
        baseline_rate: float,
        minimum_detectable_effect: float,
        confidence_level: float = 0.95,
        statistical_power: float = 0.80
    ) -> int:
        """
        Calculate minimum sample size needed per variant

        Args:
            baseline_rate: Expected baseline conversion rate (e.g., 0.05 for 5%)
            minimum_detectable_effect: Minimum % change to detect (e.g., 0.20 for 20% lift)
            confidence_level: Confidence level (default 95%)
            statistical_power: Statistical power (default 80%)

        Returns:
            Minimum sample size per variant
        """
        # Get z-scores
        z_alpha = StatisticalCalculator.get_z_critical(confidence_level, two_tailed=True)

        # Power corresponds to 1 - beta, so beta = 1 - power
        # For 80% power, we need z-score for 80th percentile
        power_z_table = {
            0.80: 0.84,
            0.90: 1.28,
            0.95: 1.645
        }
        z_beta = power_z_table.get(statistical_power, 0.84)

        # Expected variant rate
        p1 = baseline_rate
        p2 = baseline_rate * (1 + minimum_detectable_effect)

        # Pooled rate
        p_avg = (p1 + p2) / 2

        # Sample size formula
        numerator = (z_alpha * math.sqrt(2 * p_avg * (1 - p_avg)) +
                     z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2

        denominator = (p2 - p1) ** 2

        n = numerator / denominator

        return int(math.ceil(n))

    def calculate_significance(
        self,
        control_conversions: int,
        control_impressions: int,
        variant_conversions: int,
        variant_impressions: int,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Complete statistical analysis of variant vs control

        Returns comprehensive significance results including:
        - Is significant (yes/no)
        - P-value
        - Z-score
        - Confidence intervals
        - Relative lift
        - Sample sizes
        """

        # Calculate conversion rates
        control_rate = self.calculate_conversion_rate(control_conversions, control_impressions)
        variant_rate = self.calculate_conversion_rate(variant_conversions, variant_impressions)

        # Calculate z-score and p-value
        z_score = self.calculate_z_score(
            control_conversions,
            control_impressions,
            variant_conversions,
            variant_impressions
        )

        p_value = self.z_to_p_value(z_score, two_tailed=True)

        # Determine significance
        alpha = 1 - confidence_level
        is_significant = p_value < alpha

        # Calculate confidence intervals
        control_ci = self.calculate_confidence_interval(
            control_conversions,
            control_impressions,
            confidence_level
        )

        variant_ci = self.calculate_confidence_interval(
            variant_conversions,
            variant_impressions,
            confidence_level
        )

        # Calculate lift
        lift = self.calculate_relative_lift(
            control_conversions,
            control_impressions,
            variant_conversions,
            variant_impressions
        )

        return {
            "is_significant": is_significant,
            "confidence_level": confidence_level,
            "p_value": round(p_value, 4),
            "z_score": round(z_score, 4),
            "control": {
                "conversion_rate": round(control_rate, 2),
                "conversions": control_conversions,
                "impressions": control_impressions,
                "confidence_interval": {
                    "lower": round(control_ci[0], 2),
                    "upper": round(control_ci[1], 2)
                }
            },
            "variant": {
                "conversion_rate": round(variant_rate, 2),
                "conversions": variant_conversions,
                "impressions": variant_impressions,
                "confidence_interval": {
                    "lower": round(variant_ci[0], 2),
                    "upper": round(variant_ci[1], 2)
                }
            },
            "relative_lift": round(lift, 2),
            "interpretation": self._get_interpretation(is_significant, lift, p_value)
        }

    @staticmethod
    def _get_interpretation(is_significant: bool, lift: float, p_value: float) -> str:
        """Generate human-readable interpretation of results"""
        if not is_significant:
            return f"No statistically significant difference detected (p={p_value:.4f}). Need more data."

        direction = "increase" if lift > 0 else "decrease"
        return f"Statistically significant {abs(lift):.1f}% {direction} detected (p={p_value:.4f})."
