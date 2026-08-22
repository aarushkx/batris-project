"""
State-of-Health (SOH) prediction model.

This file uses two XGBoost models:

1. Point model
   Predicts the main SOH value.

2. Quantile model
   Predicts a lower and upper range for the SOH prediction.
   This gives us a 90% prediction interval.

For example:

    SOH = 0.83
    90% interval = 0.79 - 0.87

This is important because the SOH value is an estimate, not a certified
laboratory measurement. Showing the uncertainty makes this difference clear.

There are two model versions:

``full``
    Uses all available SOH features, including battery usage history such
    as cycle count, total usage and battery age.

``provenance_free``
    Uses only features that do not depend on the battery's past history.

    It removes:
    - Features that need battery history.
    - Features that need a healthy starting baseline.
    - Features that depend on the charging equipment or charging method.

This version is useful for used batteries where the previous history is
unknown or cannot be trusted. It focuses more on the battery's current
condition.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from ..features import (
    PROTOCOL_DEPENDENT,
    REQUIRES_BASELINE,
    REQUIRES_HISTORY,
    SOH_FEATURES,
    assert_no_leakage,
    feature_group_of,
)

logger = logging.getLogger(__name__)


# Quantiles used to create the prediction interval.
QUANTILES = [0.05, 0.50, 0.95]


# Default XGBoost settings.
# The dataset is relatively small, so we use smaller trees
# and regularization to reduce overfitting.
DEFAULT_PARAMS: Dict = {
    "n_estimators": 500,
    "max_depth": 4,
    "learning_rate": 0.04,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "min_child_weight": 5,
    "reg_lambda": 2.0,
    "reg_alpha": 0.1,
    "random_state": 42,
    "n_jobs": 4,
}


# Different versions of the SOH model.
VARIANTS = ("full", "provenance_free")


def features_for_variant(variant: str) -> List[str]:
    """Return the features that should be used for a model variant."""

    # Tier models have their own feature list.
    if variant.startswith("tier_"):
        return []

    # Full model uses every allowed SOH feature.
    if variant == "full":
        return list(SOH_FEATURES)

    # Provenance-free model removes features that need history,
    # a baseline or a specific charging protocol.
    if variant == "provenance_free":
        excluded = (
            PROTOCOL_DEPENDENT |
            REQUIRES_BASELINE |
            REQUIRES_HISTORY
        )

        return [
            f
            for f in SOH_FEATURES
            if f not in excluded
        ]

    raise ValueError(
        f"Unknown variant {variant!r}. Use one of {VARIANTS}."
    )


@dataclass
class SOHPrediction:
    """Store one SOH prediction and its extra information."""

    soh: float

    # Lower and upper limits of the 90% prediction interval.
    soh_lower: float
    soh_upper: float

    interval_width: float

    # Effect of each individual feature.
    contributions: Dict[str, float] = field(
        default_factory=dict
    )

    # Effect of each larger degradation group.
    group_contributions: Dict[str, float] = field(
        default_factory=dict
    )

    def as_dict(self) -> Dict:
        """Convert the prediction into a dictionary."""

        return {
            "soh": round(self.soh, 4),

            "soh_percent":
                round(100 * self.soh, 2),

            "confidence_interval_90": [
                round(self.soh_lower, 4),
                round(self.soh_upper, 4)
            ],

            "interval_width":
                round(self.interval_width, 4),
        }


class SOHModel:
    """Train, use, save and load the SOH model."""

    def __init__(
        self,
        variant: str = "full",
        params: Optional[Dict] = None
    ):
        self.variant = variant

        # Decide which features this model will use.
        self.features = features_for_variant(
            variant
        )

        # Combine default settings with any custom settings.
        self.params = {
            **DEFAULT_PARAMS,
            **(params or {})
        }

        self.point_model: Optional[
            xgb.XGBRegressor
        ] = None

        self.quantile_model: Optional[
            xgb.XGBRegressor
        ] = None

        self.metadata: Dict = {}

        # Used to widen the prediction interval if calibration
        # shows that the original interval is too narrow.
        self.calibration_factor: float = 1.0

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        df: pd.DataFrame,
        verbose: bool = False
    ) -> "SOHModel":
        """Train the SOH models using the feature table."""

        # Make sure no discharge-based target data is being used
        # as a model input.
        assert_no_leakage(self.features)

        # Select model inputs and the SOH target.
        X = df[self.features]
        y = df["soh"].to_numpy()

        # Only keep rows where SOH is available.
        mask = np.isfinite(y)

        X = X[mask]
        y = y[mask]

        # Main model that predicts one SOH value.
        self.point_model = xgb.XGBRegressor(
            objective="reg:squarederror",
            **self.params
        )

        self.point_model.fit(
            X,
            y,
            verbose=verbose
        )

        # Second model predicts the 5%, 50% and 95% quantiles.
        self.quantile_model = xgb.XGBRegressor(
            objective="reg:quantileerror",
            quantile_alpha=QUANTILES,
            **self.params
        )

        self.quantile_model.fit(
            X,
            y,
            verbose=verbose
        )

        # Store information about how the model was trained.
        self.metadata = {
            "variant": self.variant,
            "features": self.features,
            "n_features": len(self.features),
            "n_training_cycles": int(len(y)),
            "training_batteries":
                sorted(
                    df.loc[
                        mask,
                        "battery_id"
                    ].unique().tolist()
            ),
            "training_formats":
                sorted(
                    df.loc[
                        mask,
                        "format_key"
                    ].unique().tolist()
            ),
            "soh_train_range": [
                float(y.min()),
                float(y.max())
            ],
            "quantiles": QUANTILES,
            "params": self.params,
            "training_data_sha256":
                self._hash_frame(X, y),
            "interval_calibration_factor":
                self.calibration_factor,
        }

        return self

    @staticmethod
    def _hash_frame(
        X: pd.DataFrame,
        y: np.ndarray
    ) -> str:
        """Create a short hash of the training data."""

        digest = hashlib.sha256()

        # Add the input features to the hash.
        digest.update(
            np.ascontiguousarray(
                X.to_numpy(dtype=float)
            ).tobytes()
        )

        # Add the target values to the hash.
        digest.update(
            np.ascontiguousarray(y).tobytes()
        )

        return digest.hexdigest()[:16]

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        df: pd.DataFrame
    ) -> np.ndarray:
        """Return the main SOH prediction."""

        self._check_fitted()

        return self.point_model.predict(
            df[self.features]
        )

    def predict_interval(
        self,
        df: pd.DataFrame,
        calibrated: bool = True
    ) -> np.ndarray:
        """Return lower, middle and upper SOH values."""

        self._check_fitted()

        # Get the 5%, 50% and 95% predictions.
        q = np.asarray(
            self.quantile_model.predict(
                df[self.features]
            )
        )

        # Make sure the array has three columns.
        if q.ndim == 1:
            q = np.column_stack([
                q,
                q,
                q
            ])

        # Make sure the quantiles are in the correct order.
        q = np.sort(q, axis=1)

        # Get the main point prediction.
        point = np.asarray(
            self.point_model.predict(
                df[self.features]
            ),
            dtype=float
        )

        # Calculate the lower and upper distance from the median.
        lower_half = np.maximum(
            q[:, 1] - q[:, 0],
            0.0
        )

        upper_half = np.maximum(
            q[:, 2] - q[:, 1],
            0.0
        )

        # Increase the interval if calibration requires it.
        if calibrated:
            lower_half *= self.calibration_factor
            upper_half *= self.calibration_factor

        # Return:
        # lower bound, point estimate, upper bound.
        #
        # The values are also kept between 0 and 1.05.
        return np.clip(
            np.column_stack([
                point - lower_half,
                point,
                point + upper_half
            ]),
            0.0,
            1.05
        )

    def calibrate(
        self,
        residual_ratios: np.ndarray,
        target_coverage: float = 0.90
    ) -> float:
        """Adjust the prediction interval using validation errors."""

        ratios = np.asarray(
            residual_ratios,
            dtype=float
        )

        # Remove invalid values.
        ratios = ratios[
            np.isfinite(ratios)
        ]

        if ratios.size == 0:
            return self.calibration_factor

        # Do not make the interval smaller than the original one.
        self.calibration_factor = float(
            max(
                1.0,
                np.quantile(
                    ratios,
                    target_coverage
                )
            )
        )

        return self.calibration_factor

    def explain(
        self,
        df: pd.DataFrame
    ) -> tuple[np.ndarray, float]:
        """Calculate how much each feature affected the prediction."""

        self._check_fitted()

        # Get the trained XGBoost model.
        booster = self.point_model.get_booster()

        # Convert the dataframe into an XGBoost data object.
        dmatrix = xgb.DMatrix(
            df[self.features],
            feature_names=self.features
        )

        # Ask XGBoost for the SHAP contributions.
        raw = np.asarray(
            booster.predict(
                dmatrix,
                pred_contribs=True
            )
        )

        # Handle multi-output shape if needed.
        if raw.ndim == 3:
            raw = raw[:, 0, :]

        # The last column is the base value,
        # so return only the feature contributions.
        return (
            raw[:, :-1],
            float(raw[0, -1])
        )

    def predict_full(
        self,
        df: pd.DataFrame
    ) -> List[SOHPrediction]:
        """Return prediction, uncertainty and explanations together."""

        point = self.predict(df)

        interval = self.predict_interval(df)

        contribs, _ = self.explain(df)

        results = []

        for i in range(len(df)):

            # Store the contribution of every feature.
            per_feature = {
                name: float(
                    contribs[i, j]
                )
                for j, name
                in enumerate(self.features)
            }

            # Combine individual features into larger
            # degradation groups.
            per_group: Dict[str, float] = {}

            for name, value in per_feature.items():

                group = feature_group_of(
                    name
                )

                per_group.setdefault(
                    group,
                    0.0
                )

                per_group[group] += value

            results.append(
                SOHPrediction(
                    soh=float(point[i]),

                    soh_lower=float(
                        interval[i, 0]
                    ),

                    soh_upper=float(
                        interval[i, 2]
                    ),

                    interval_width=float(
                        interval[i, 2] -
                        interval[i, 0]
                    ),

                    contributions=per_feature,

                    group_contributions=per_group,
                )
            )

        return results

    def feature_importance(
        self
    ) -> pd.Series:
        """Return the most important features."""

        self._check_fitted()

        # Get the importance values from XGBoost.
        gains = self.point_model.get_booster().get_score(
            importance_type="gain"
        )

        series = pd.Series(
            {
                f: gains.get(f, 0.0)
                for f in self.features
            },
            dtype=float
        )

        # Convert values into relative percentages.
        total = series.sum()

        if total > 0:
            series = series / total

        return series.sort_values(
            ascending=False
        )

    def _check_fitted(self) -> None:
        """Make sure the models have already been trained."""

        if (
            self.point_model is None
            or self.quantile_model is None
        ):
            raise RuntimeError(
                "Model is not fitted. "
                "Call fit() or load() first."
            )

    # ------------------------------------------------------------------
    # Saving and loading
    # ------------------------------------------------------------------

    def save(
        self,
        directory: Path | str
    ) -> Path:
        """Save the trained models and their information."""

        self._check_fitted()

        directory = Path(directory)

        # Create the folder if needed.
        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        # Save both XGBoost models and their settings.
        joblib.dump(
            {
                "point_model":
                    self.point_model,

                "quantile_model":
                    self.quantile_model,

                "variant":
                    self.variant,

                "features":
                    self.features,

                "params":
                    self.params,

                "calibration_factor":
                    self.calibration_factor,
            },
            directory /
            f"soh_{self.variant}.joblib",
        )

        # Save additional information separately as JSON.
        with open(
            directory /
            f"soh_{self.variant}_meta.json",
            "w",
            encoding="utf-8"
        ) as fh:

            json.dump(
                self.metadata,
                fh,
                indent=2
            )

        logger.info(
            "Saved SOH model (%s) to %s",
            self.variant,
            directory
        )

        return (
            directory /
            f"soh_{self.variant}.joblib"
        )

    @classmethod
    def load(
        cls,
        directory: Path | str,
        variant: str = "full"
    ) -> "SOHModel":
        """Load an already trained SOH model."""

        directory = Path(directory)

        path = (
            directory /
            f"soh_{variant}.joblib"
        )

        if not path.exists():
            raise FileNotFoundError(
                f"No trained model at {path}. "
                "Run: python -m backend.batris.train_soh"
            )

        # Load the saved model.
        blob = joblib.load(path)

        model = cls(
            variant=blob["variant"],
            params=blob["params"]
        )

        # Restore everything needed for prediction.
        model.point_model = blob["point_model"]
        model.quantile_model = blob["quantile_model"]
        model.features = blob["features"]

        model.calibration_factor = float(
            blob.get(
                "calibration_factor",
                1.0
            )
        )

        # Load the metadata if it exists.
        meta_path = (
            directory /
            f"soh_{variant}_meta.json"
        )

        if meta_path.exists():
            with open(
                meta_path,
                "r",
                encoding="utf-8"
            ) as fh:

                model.metadata = json.load(fh)

        return model
