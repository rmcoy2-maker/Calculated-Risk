import math
import numpy as np
import pandas as pd
from typing import Optional

def grade_row(row: pd.Series) -> Optional[str]:
    # market / side
    market = norm_cell(row.get("market")).lower()
    side   = norm_cell(row.get("side") or row.get("selection"))

    # teams
    home = norm_cell(row.get("home") or row.get("team_home") or row.get("hometeam") or row.get("home_team_g"))
    away = norm_cell(row.get("away") or row.get("team_away") or row.get("awayteam") or row.get("away_team_g"))

    # scores
    h = to_float(row.get("home_score") or row.get("home_score_y") or row.get("home_score_g")
                 or row.get("homescore") or row.get("homescore.1") or row.get("score_home"))
    a = to_float(row.get("away_score") or row.get("away_score_y") or row.get("away_score_g")
                 or row.get("awayscore") or row.get("awayscore.1") or row.get("score_away"))

    if np.isnan(h) or np.isnan(a):
        return None

    if market == "moneyline":
        if side == home:
            return "win" if h > a else "loss" if h < a else "push"
        if side == away:
            return "win" if a > h else "loss" if a < h else "push"
        return None

    if market == "spread":
        line = to_float(row.get("line"))
        if np.isnan(line): return None
        if side == home:
            margin = h - a
        elif side == away:
            margin = a - h
        else:
            return None
        diff = margin - (-line)
        if math.isclose(diff, 0.0, abs_tol=1e-9):
            return "push"
        return "win" if diff > 0 else "loss"

    if market == "total":
        line = to_float(row.get("line"))
        if np.isnan(line): return None
        tp = total_points(row)
        if tp is None: return None
        if math.isclose(tp, line, abs_tol=1e-9):
            return "push"
        if side == "OVER":
            return "win" if tp > line else "loss"
        if side == "UNDER":
            return "win" if tp < line else "loss"
        return None

    return None

