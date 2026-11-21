"""Check my data: calibration maths for Tools -> Threshold simulator -> My data. Pure Python, runs in the browser.

The rows people paste or pick never leave the page: nothing here calls the server or writes browser storage.

    parse(text)                       CSV text -> {"rows": [(confidence, correct)], "skipped", "used", "error", "fmt", "notes"}
    stats(rows)                       accuracy, ECE (10 bins), Brier, the reliability bins and the high-confidence band
    prefix(rows)                      counts at or above every 0.01 step (fast slider maths for 20,000 rows)
    cheapest(rows, err, review)       the act-automatically threshold with the lowest total cost (grid 0.50 to 0.99)
    sample_csv(rows)                  the sample data as "confidence,correct" CSV text

Formats (header optional; comma, semicolon or tab):
    confidence,correct                correct = 1/0, true/false, yes/no, y/n, right/wrong, correct/incorrect
    predicted,actual,confidence       correct = predicted equals actual (case and spaces ignored)
Confidence 0 to 1, or 0 to 100 (percent) when any value is above 1.
"""
import math

MIN_ROWS = 50
MAX_ROWS = 20000
BINS = 10

TRUE_WORDS = ("1", "true", "yes", "y", "t", "right", "correct", "ok", "1.0")
FALSE_WORDS = ("0", "false", "no", "n", "f", "wrong", "incorrect", "0.0")
CONF_NAMES = ("confidence", "conf", "probability", "prob", "p", "score", "p_max", "pmax", "certainty")
CORRECT_NAMES = ("correct", "is_correct", "right", "ok", "match", "hit", "accurate")
PRED_NAMES = ("predicted", "prediction", "pred", "choice", "answer", "output", "jev")
ACTUAL_NAMES = ("actual", "label", "truth", "gold", "expected", "true_label", "human", "target")


def _split(line, delim):
    """One CSV line -> fields (double quotes may wrap a field and hold the delimiter; "" is a quote)."""
    if '"' not in line:  # the fast path: almost every line
        return [f.strip() for f in line.split(delim)]
    out, cur, quoted, i = [], [], False, 0
    while i < len(line):
        ch = line[i]
        if quoted:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    cur.append('"')
                    i += 1
                else:
                    quoted = False
            else:
                cur.append(ch)
        elif ch == '"':
            quoted = True
        elif ch == delim:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur).strip())
    return out


def _delimiter(lines):
    best, best_n = ",", -1
    for d in (",", ";", "\t"):
        n = sum(1 for ln in lines[:20] if d in ln)
        if n > best_n:
            best, best_n = d, n
    return best


def _number(text, comma_decimal):
    s = (text or "").strip().rstrip("%").strip()
    if comma_decimal:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v == v else None  # NaN is not a number here


def _correct(text):
    s = (text or "").strip().lower()
    if s in TRUE_WORDS:
        return True
    if s in FALSE_WORDS:
        return False
    return None


def _find(names, wanted):
    for i, h in enumerate(names):
        if h in wanted:
            return i
    return None


def parse(text):
    """CSV text -> rows of (confidence 0..1, correct bool). Lines that can't be read are counted, not fatal."""
    res = {"rows": [], "skipped": 0, "used": 0, "error": None, "fmt": "", "notes": []}
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    lines = [ln for ln in raw.split("\n") if ln.strip()]
    if not lines:
        res["error"] = "Paste some rows first, or pick a .csv file."
        return res
    delim = _delimiter(lines)
    comma_decimal = delim != ","
    first = [f.lower().replace(" ", "_") for f in _split(lines[0], delim)]
    has_header = all(_number(f, comma_decimal) is None for f in first) and not all(_correct(f) is not None for f in first)
    ci = ki = pi = ai = None
    if has_header:
        ci, ki = _find(first, CONF_NAMES), _find(first, CORRECT_NAMES)
        pi, ai = _find(first, PRED_NAMES), _find(first, ACTUAL_NAMES)
        lines = lines[1:]
    width = len(first)
    if ci is None or (ki is None and (pi is None or ai is None)):
        # no usable names: by position
        if width >= 3:
            pi, ai, ci, ki = 0, 1, 2, None
        else:
            ci, ki, pi, ai = 0, 1, None, None
    three = ki is None
    res["fmt"] = "predicted,actual,confidence" if three else "confidence,correct"
    vals = []
    for ln in lines:
        f = _split(ln, delim)
        need = max([x for x in (ci, ki, pi, ai) if x is not None])
        if len(f) <= need:
            res["skipped"] += 1
            continue
        c = _number(f[ci], comma_decimal)
        if three:
            ok = None if not f[pi] or not f[ai] else " ".join(f[pi].lower().split()) == " ".join(f[ai].lower().split())
        else:
            ok = _correct(f[ki])
        if c is None or ok is None or c < 0 or c > 100:
            res["skipped"] += 1
            continue
        vals.append((c, ok))
    if vals and max(v[0] for v in vals) > 1:
        vals = [(c / 100.0, ok) for c, ok in vals]
        res["notes"].append("Confidence read as percent (values above 1).")
    if len(vals) > MAX_ROWS:
        res["notes"].append("Used the first %s of %s rows." % (_thousands(MAX_ROWS), _thousands(len(vals))))
        vals = vals[:MAX_ROWS]
    res["used"] = len(vals)
    if len(vals) < MIN_ROWS:
        res["error"] = ("Found %d usable row%s: at least %d are needed for a fair check (a few hundred is better)."
                        % (len(vals), "" if len(vals) == 1 else "s", MIN_ROWS))
        return res
    res["rows"] = vals
    return res


def _thousands(n):
    s = str(int(n))
    out = ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    return s + out


def stats(rows):
    """Accuracy, ECE over 10 equal-width bins, Brier score, the bins themselves and the 0.9+ band."""
    n = len(rows)
    if not n:
        return None
    bins = [[0, 0, 0.0] for _ in range(BINS)]  # count, right, sum of confidence
    right, brier = 0, 0.0
    for c, ok in rows:
        b = bins[min(BINS - 1, int(math.floor(c * BINS)))]
        b[0] += 1
        b[2] += c
        if ok:
            b[1] += 1
            right += 1
        brier += (c - (1.0 if ok else 0.0)) ** 2
    out_bins, ece = [], 0.0
    for k, (cnt, r, sc) in enumerate(bins):
        acc = r * 1.0 / cnt if cnt else None
        conf = sc / cnt if cnt else None
        if cnt:
            ece += cnt * 1.0 / n * abs(acc - conf)
        out_bins.append({"lo": k * 1.0 / BINS, "hi": (k + 1) * 1.0 / BINS, "n": cnt, "acc": acc, "conf": conf})
    high = [(c, ok) for c, ok in rows if c >= 0.9]
    band = {"label": "0.9+", "lo": 0.9}
    if len(high) < 10:  # too few at 0.9+: use the highest bin that has answers
        top = [b for b in out_bins if b["n"]][-1]
        band = {"label": "%.1f to %.1f" % (top["lo"], top["hi"]), "lo": top["lo"]}
        high = [(c, ok) for c, ok in rows if top["lo"] <= c < top["hi"] or (top["hi"] >= 1 and c >= top["lo"])]
    band["n"] = len(high)
    band["acc"] = sum(1 for _, ok in high if ok) * 1.0 / len(high) if high else 0.0
    band["conf"] = sum(c for c, _ in high) / len(high) if high else 0.0
    band["gap"] = band["conf"] - band["acc"]  # > 0 = over-confident
    return {"n": n, "accuracy": right * 1.0 / n, "mean_conf": sum(c for c, _ in rows) / n, "ece": ece,
            "brier": brier / n, "bins": out_bins, "band": band}


def verdict(st):
    """One plain sentence about the high-confidence band, e.g. '0.9+ answers were right 84% of the time
    (over-confident by 9 points).'"""
    b = st["band"]
    pts = int(round(abs(b["gap"]) * 100))
    if pts <= 2:
        how = "about as often as they claimed (well calibrated there)"
    elif b["gap"] > 0:
        how = "over-confident by %d point%s" % (pts, "" if pts == 1 else "s")
    else:
        how = "under-confident by %d point%s: right more often than they claim" % (pts, "" if pts == 1 else "s")
    return "%s answers (%s of them, average confidence %.2f) were right %d%% of the time: %s." % (
        b["label"], _thousands(b["n"]), b["conf"], int(round(b["acc"] * 100)), how)


def ece_words(ece):
    """A rough reading of ECE (a rule of thumb, not a standard)."""
    if ece < 0.03:
        return "Close to calibrated: the confidence numbers can be read as hit rates."
    if ece < 0.08:
        return "Somewhat off: set thresholds from this data, not from the raw numbers."
    return "Far off: treat confidence as a ranking only and pick thresholds from this data."


def _bucket(c):
    return max(0, min(100, int(math.floor(c * 100 + 1e-9))))


def prefix(rows):
    """ge[k] = answers with confidence >= k/100, wrong_ge[k] = the wrong ones among them (k = 0..101)."""
    cnt, bad = [0] * 102, [0] * 102
    for c, ok in rows:
        k = _bucket(c)
        cnt[k] += 1
        if not ok:
            bad[k] += 1
    ge, wrong_ge = [0] * 102, [0] * 102
    for k in range(100, -1, -1):
        ge[k] = ge[k + 1] + cnt[k]
        wrong_ge[k] = wrong_ge[k + 1] + bad[k]
    return {"n": len(rows), "ge": ge, "wrong_ge": wrong_ge}


def step(t):
    """A threshold 0..1 as its 0.01 step index (0.8 -> 80)."""
    return max(0, min(101, int(math.floor(t * 100 + 0.5))))


def cost_per_10k(prep, auto_k, err_cost, review_cost):
    """The simulator's formula: mistakes that slip through x their cost + every non-automatic case x a review."""
    n = prep["n"] or 1
    wrong = prep["wrong_ge"][auto_k]
    reviewed = prep["n"] - prep["ge"][auto_k]
    return (wrong * err_cost + reviewed * review_cost) / float(n) * 10000


def cheapest(rows, err_cost, review_cost, prep=None):
    """The act-automatically threshold (0.50 to 0.99) with the lowest cost per 10k decisions; ties go to the lower
    threshold (more automation). The confirm floor follows the guide's gate.py rule: auto - 0.25, at least 0.5."""
    prep = prep or prefix(rows)
    best_k, best = 50, None
    for k in range(50, 100):
        c = cost_per_10k(prep, k, err_cost, review_cost)
        if best is None or c < best - 1e-9:
            best_k, best = k, c
    auto = best_k / 100.0
    floor = max(0.5, math.floor((auto - 0.25) * 100 + 0.5) / 100.0)
    return {"auto": auto, "floor": min(floor, auto), "cost": best}


def sample_csv(rows):
    return "confidence,correct\n" + "\n".join("%.3f,%d" % (c, 1 if ok else 0) for c, ok in rows) + "\n"
