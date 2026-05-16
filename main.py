# ═══════════════════════════════════════════════════════════════════════════════
# TaaraVaani Math Engine — FastAPI + pyswisseph
# Fixes applied vs previous version:
#   1. Ayanamsha selected via integer IDs (no AttributeError on any pyswisseph version)
#   2. `ayanamsha` field added to ProfileData — Flutter can now pass it per request
#   3. SAV key renamed "SAV (Total)" to match Flutter's _kAshtakPlanets constant
#   4. Server-level error detail now returned in `error` field for Flutter SnackBar
#   5. swe.set_sid_mode() called before julday() for clean global state
#   6. FLG_SPEED added to calc_ut for retrograde detection
#   7. /api/version endpoint added — confirms live pyswisseph version on server
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import swisseph as swe
from timezonefinder import TimezoneFinder
import pytz

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

tf = TimezoneFinder()

# ── Ayanamsha Registry ────────────────────────────────────────────────────────
# Always use integer IDs — never swe.SIDM_* named constants.
# Named constants were added at different pyswisseph versions and cause
# AttributeError on older builds, silently returning success:false to Flutter.
#
#   ID  1  = Lahiri (official, Calendar Reform Committee 1955)
#   ID  3  = Raman
#   ID 27  = True Chitrapaksha (Spica fixed at exact 180°) — Swiss Eph 2.x+
#
AYANAMSHA_MAP: dict[str, int] = {
    "lahiri":     1,
    "raman":      3,
    "true_citra": 27,   # True Chitrapaksha — recommended for precision work
}
DEFAULT_AYANAMSHA = "true_citra"

# ── Request Model ─────────────────────────────────────────────────────────────
class ProfileData(BaseModel):
    name:      str
    dob:       str            # "YYYY-MM-DD"
    time:      str            # "HH:MM" or "HH:MM:SS"
    lat:       float
    lng:       float
    ayanamsha: Optional[str] = DEFAULT_AYANAMSHA  # "lahiri" | "raman" | "true_citra"

# ── Static Lookup Tables ──────────────────────────────────────────────────────
ASHTAKVARGA_RULES = {
    "Sun":     {"Sun": [0,1,3,6,7,8,9,10],     "Moon": [2,5,9,10],         "Mars": [0,1,3,6,7,8,9,10],    "Mercury": [2,4,5,8,9,10,11],      "Jupiter": [4,5,8,10],        "Venus": [5,6,11],              "Saturn": [0,1,3,6,7,8,9,10],  "Asc": [2,3,5,9,10,11]},
    "Moon":    {"Sun": [2,5,6,7,9,10],          "Moon": [0,2,5,6,9,10],     "Mars": [1,2,4,5,8,9,10],      "Mercury": [0,2,3,4,6,7,9,10],    "Jupiter": [0,3,6,7,9,10,11], "Venus": [2,3,4,6,8,9,10],      "Saturn": [2,4,5,10],          "Asc": [2,5,9,10]},
    "Mars":    {"Sun": [2,4,5,9,10],            "Moon": [2,5,10],           "Mars": [0,1,3,6,7,9,10],      "Mercury": [2,4,5,10],             "Jupiter": [5,9,10,11],       "Venus": [5,7,10,11],           "Saturn": [0,3,6,7,8,9,10],    "Asc": [0,2,5,9,10]},
    "Mercury": {"Sun": [4,5,8,10,11],           "Moon": [1,3,5,7,9,10],     "Mars": [0,1,3,6,7,8,9,10],    "Mercury": [0,2,4,5,8,9,10,11],   "Jupiter": [5,7,10,11],       "Venus": [0,1,2,3,4,7,8,10],    "Saturn": [0,1,3,6,7,8,9,10],  "Asc": [0,1,3,5,7,9,10]},
    "Jupiter": {"Sun": [0,1,2,3,6,7,8,9,10],   "Moon": [1,4,6,8,10],       "Mars": [0,1,3,6,7,9,10],      "Mercury": [0,1,3,4,5,8,9,10],    "Jupiter": [0,1,2,3,6,7,9,10],"Venus": [1,4,5,8,9,10],        "Saturn": [2,4,5,11],          "Asc": [0,1,3,4,5,6,8,9,10]},
    "Venus":   {"Sun": [7,10,11],               "Moon": [0,1,2,3,4,7,8,10,11],"Mars": [2,4,5,8,10,11],    "Mercury": [2,4,5,8,10],           "Jupiter": [4,7,8,9,10],      "Venus": [0,1,2,3,4,7,8,9,10],  "Saturn": [2,3,4,7,8,9,10],    "Asc": [0,1,2,3,4,7,8,10]},
    "Saturn":  {"Sun": [0,1,3,6,7,9,10],        "Moon": [2,5,10],           "Mars": [2,4,5,9,10,11],       "Mercury": [5,7,8,9,10,11],        "Jupiter": [4,5,10,11],       "Venus": [5,10,11],             "Saturn": [2,4,5,10],          "Asc": [0,2,3,5,9,10]},
}

TITHIS = [
    'Pratipada','Dwitiya','Tritiya','Chaturthi','Panchami','Shashthi',
    'Saptami','Ashtami','Navami','Dashami','Ekadashi','Dwadashi',
    'Trayodashi','Chaturdashi','Purnima',
    'Pratipada (K)','Dwitiya (K)','Tritiya (K)','Chaturthi (K)','Panchami (K)',
    'Shashthi (K)','Saptami (K)','Ashtami (K)','Navami (K)','Dashami (K)',
    'Ekadashi (K)','Dwadashi (K)','Trayodashi (K)','Chaturdashi (K)','Amavasya',
]
NAKSHATRAS = [
    'Ashwini','Bharani','Krittika','Rohini','Mrigashirsha','Ardra',
    'Punarvasu','Pushya','Ashlesha','Magha','Purva Phalguni','Uttara Phalguni',
    'Hasta','Chitra','Swati','Vishakha','Anuradha','Jyeshtha','Moola',
    'Purva Ashadha','Uttara Ashadha','Shravana','Dhanishta','Shatabhisha',
    'Purva Bhadrapada','Uttara Bhadrapada','Revati',
]
ZODIAC_SIGNS = [
    'Aries','Taurus','Gemini','Cancer','Leo','Virgo',
    'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces',
]
SIGN_LORDS = ["Mars","Venus","Mercury","Moon","Sun","Mercury","Venus","Mars","Jupiter","Saturn","Saturn","Jupiter"]
NAK_LORDS  = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]

# ── KP Sub-lord Calculator ────────────────────────────────────────────────────
def get_kp_lords(deg: float):
    sign_lord  = SIGN_LORDS[int(deg / 30) % 12]
    nak_span   = 13 + (20 / 60)          # 13°20' per nakshatra
    nak_idx    = int(deg / nak_span)
    star_lord  = NAK_LORDS[nak_idx % 9]
    deg_in_nak = deg - (nak_idx * nak_span)
    min_in_nak = deg_in_nak * 60
    curr, acc  = nak_idx % 9, 0.0
    sub_lord   = NAK_LORDS[curr]
    years      = [7, 20, 6, 10, 7, 18, 16, 19, 17]   # Vimshottari Dasha years
    for _ in range(9):
        span = (years[curr] / 120) * 800
        if min_in_nak < acc + span:
            sub_lord = NAK_LORDS[curr]
            break
        acc += span
        curr = (curr + 1) % 9
    return sign_lord, star_lord, sub_lord

# ── Planetary Dignity ─────────────────────────────────────────────────────────
def get_planetary_status(se_id: int, sign: int) -> str:
    own        = {swe.SUN:[4], swe.MOON:[3], swe.MARS:[0,7], swe.MERCURY:[2,5], swe.JUPITER:[8,11], swe.VENUS:[1,6], swe.SATURN:[9,10]}
    exalted    = {swe.SUN:0, swe.MOON:1, swe.MARS:9, swe.MERCURY:5, swe.JUPITER:3, swe.VENUS:11, swe.SATURN:6}
    debilitated= {swe.SUN:6, swe.MOON:7, swe.MARS:3, swe.MERCURY:11, swe.JUPITER:9, swe.VENUS:5, swe.SATURN:0}
    if se_id in exalted     and sign == exalted[se_id]:     return "Exalted"
    if se_id in debilitated and sign == debilitated[se_id]: return "Debilitated"
    if se_id in own         and sign in own[se_id]:         return "Own Sign"
    return "Neutral"

# ── Varga (Divisional Chart) Sign Calculator ──────────────────────────────────
def get_varga_sign(degree: float, varga: int) -> int:
    sign       = int(degree // 30)
    deg_in_sign= degree % 30

    if varga == 2:
        return 4 if (sign % 2 == 0 and deg_in_sign < 15) else \
               3 if (sign % 2 == 0) else \
               3 if deg_in_sign < 15 else 4

    elif varga == 3:
        return (sign + int(deg_in_sign // 10) * 4) % 12

    elif varga == 4:
        return (sign + int(deg_in_sign // 7.5) * 3) % 12

    elif varga == 7:
        start = sign if sign % 2 == 0 else (sign + 6) % 12
        return (start + int(deg_in_sign // (30 / 7))) % 12

    elif varga == 9:
        return int((degree * 9) // 30) % 12

    elif varga == 10:
        start = sign if sign % 2 == 0 else (sign + 8) % 12
        return (start + int(deg_in_sign // 3)) % 12

    elif varga == 12:
        return (sign + int(deg_in_sign // 2.5)) % 12

    elif varga == 16:
        mod3  = sign % 3
        start = 0 if mod3 == 0 else (4 if mod3 == 1 else 8)
        return (start + int(deg_in_sign // (30 / 16))) % 12

    elif varga == 20:
        mod3  = sign % 3
        start = 0 if mod3 == 0 else (8 if mod3 == 1 else 4)
        return (start + int(deg_in_sign // 1.5)) % 12

    elif varga == 24:
        start = 4 if sign % 2 == 0 else 3
        return (start + int(deg_in_sign // 1.25)) % 12

    elif varga == 27:
        mod4  = sign % 4
        start = 0 if mod4 == 0 else (3 if mod4 == 1 else (6 if mod4 == 2 else 9))
        return (start + int(deg_in_sign // (30 / 27))) % 12

    elif varga == 30:
        d = deg_in_sign
        if sign % 2 == 0:
            if d < 5:   return 0
            elif d < 10:return 10
            elif d < 18:return 8
            elif d < 25:return 2
            else:       return 6
        else:
            if d < 5:   return 1
            elif d < 12:return 5
            elif d < 20:return 11
            elif d < 25:return 9
            else:       return 7

    elif varga == 40:
        start = 0 if sign % 2 == 0 else 6
        return (start + int(deg_in_sign // 0.75)) % 12

    elif varga == 45:
        mod3  = sign % 3
        start = 0 if mod3 == 0 else (4 if mod3 == 1 else 8)
        return (start + int(deg_in_sign // (30 / 45))) % 12

    elif varga == 60:
        return (sign + int(deg_in_sign * 2)) % 12

    return sign  # fallback — should never hit this

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/kundali")
async def generate_kundali(data: ProfileData):
    try:
        # ── 1. Resolve timezone & UTC datetime ───────────────────────────────
        tz_str   = tf.timezone_at(lng=data.lng, lat=data.lat) or 'Asia/Kolkata'
        local_tz = pytz.timezone(tz_str)

        year, month, day          = map(int, data.dob.split('-'))
        hour, minute, sec         = map(int, (data.time + ':00').split(':')[:3])

        local_dt = local_tz.localize(datetime(year, month, day, hour, minute, sec))
        utc_dt   = local_dt.astimezone(pytz.utc)

        # ── 2. Set Ayanamsha (ALWAYS use integer ID — never swe.SIDM_* constant) ──
        # swe.SIDM_* named constants were added at different pyswisseph versions.
        # Using the integer directly works on every pyswisseph build from 1.x onward.
        requested_ayanamsha = (data.ayanamsha or DEFAULT_AYANAMSHA).lower().strip()
        sid_mode_id         = AYANAMSHA_MAP.get(requested_ayanamsha, AYANAMSHA_MAP[DEFAULT_AYANAMSHA])
        swe.set_sid_mode(sid_mode_id)   # ← must be called before any swe calculation

        # ── 3. Julian Day ─────────────────────────────────────────────────────
        julday   = swe.julday(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
        )
        ayanamsa = swe.get_ayanamsa_ut(julday)

        # ── 4. Lagna (Ascendant) ──────────────────────────────────────────────
        # houses_ex returns TROPICAL cusps; we subtract ayanamsa to get sidereal.
        houses, ascmc = swe.houses_ex(julday, data.lat, data.lng, b'P')   # 'P' = Placidus
        asc_deg_trop  = ascmc[0]
        asc_deg       = (asc_deg_trop - ayanamsa) % 360
        asc_sign      = int(asc_deg // 30)

        # ── 5. Planets ────────────────────────────────────────────────────────
        vargas = [2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60]

        bodies = [
            (swe.SUN,       'Su', 'Sun'),
            (swe.MOON,      'Mo', 'Moon'),
            (swe.MARS,      'Ma', 'Mars'),
            (swe.MERCURY,   'Me', 'Mercury'),
            (swe.JUPITER,   'Ju', 'Jupiter'),
            (swe.VENUS,     'Ve', 'Venus'),
            (swe.SATURN,    'Sa', 'Saturn'),
            (swe.TRUE_NODE, 'Ra', 'Rahu'),
        ]

        # FLG_SIDEREAL applies the active sid_mode ayanamsha automatically.
        # FLG_SPEED gives us the daily motion — negative = retrograde.
        CALC_FLAGS = swe.FLG_SIDEREAL | swe.FLG_SWIEPH | swe.FLG_SPEED

        planet_degrees   = {}
        planet_details_out = []
        planetary_signs  = {"Asc": asc_sign}
        sun_lon = moon_lon = 0.0

        for se_id, label, name in bodies:
            res, _  = swe.calc_ut(julday, se_id, CALC_FLAGS)
            lon     = res[0] % 360          # sidereal longitude 0–360°
            speed   = res[3]                # deg/day; negative = retrograde
            is_retro= speed < 0

            planet_degrees[label] = lon
            sign    = int(lon // 30)

            if se_id == swe.SUN:  sun_lon  = lon
            if se_id == swe.MOON: moon_lon = lon
            if se_id != swe.TRUE_NODE:
                planetary_signs[name] = sign

            d_in_sign  = lon % 30
            nak_idx_p  = int(lon / (360 / 27))
            sl, stl, subl = get_kp_lords(lon)
            status     = get_planetary_status(se_id, sign) if se_id != swe.TRUE_NODE else "--"
            house      = ((sign - asc_sign) % 12) + 1
            retro_str  = " (R)" if is_retro else ""

            planet_details_out.append({
                "Planet":     label + retro_str,
                "Sign":       ZODIAC_SIGNS[sign],
                "Sign Lord":  sl,
                "Nakshatra":  NAKSHATRAS[nak_idx_p],
                "Naksh Lord": stl,
                "Degree":     f"{int(d_in_sign)}°{int((d_in_sign % 1) * 60)}'",
                "House":      str(house),
                "Status":     status,
            })

            # Ketu — exact opposite of Rahu
            if se_id == swe.TRUE_NODE:
                k_lon       = (lon + 180) % 360
                k_sign      = int(k_lon // 30)
                planet_degrees["Ke"] = k_lon
                k_d_in_sign = k_lon % 30
                k_nak_idx   = int(k_lon / (360 / 27))
                k_sl, k_stl, k_subl = get_kp_lords(k_lon)
                k_house     = ((k_sign - asc_sign) % 12) + 1

                planet_details_out.append({
                    "Planet":     "Ke",
                    "Sign":       ZODIAC_SIGNS[k_sign],
                    "Sign Lord":  k_sl,
                    "Nakshatra":  NAKSHATRAS[k_nak_idx],
                    "Naksh Lord": k_stl,
                    "Degree":     f"{int(k_d_in_sign)}°{int((k_d_in_sign % 1) * 60)}'",
                    "House":      str(k_house),
                    "Status":     "--",
                })

        sun_sign  = int(sun_lon  // 30)
        moon_sign = int(moon_lon // 30)

        # ── 6. Bhav Chalit (true cusp-based house boundaries) ─────────────────
        # Each boundary = (tropical cusp − ayanamsa) mod 360 → sidereal
        chalit_houses = [(houses[i] - ayanamsa) % 360 for i in range(12)]

        # ── 7. D1 chart arrays (signs-based & house-based) ────────────────────
        chart_houses = [""] * 12
        chart_signs  = [""] * 12

        def add_planet_d1(sign_idx: int, lbl: str):
            house_idx = (sign_idx - asc_sign) % 12
            if chart_houses[house_idx]: chart_houses[house_idx] += ", "
            chart_houses[house_idx] += lbl
            if chart_signs[sign_idx]:  chart_signs[sign_idx]  += ", "
            chart_signs[sign_idx] += lbl

        add_planet_d1(asc_sign, "As")

        # ── 8. Divisional chart maps ───────────────────────────────────────────
        asc_map = {f"D{v}": get_varga_sign(asc_deg, v) for v in vargas}
        asc_map["Sun"]   = sun_sign
        asc_map["Moon"]  = moon_sign
        asc_map["Chalit"]= asc_sign

        div_charts = {k: {"signs": [""] * 12, "houses": [""] * 12} for k in asc_map}

        def add_to_div(chart_name: str, p_sign: int, lbl: str):
            a_sign = asc_map[chart_name]
            h_idx  = (p_sign - a_sign) % 12
            if div_charts[chart_name]["signs"][p_sign]:  div_charts[chart_name]["signs"][p_sign]  += ", "
            div_charts[chart_name]["signs"][p_sign]  += lbl
            if div_charts[chart_name]["houses"][h_idx]: div_charts[chart_name]["houses"][h_idx] += ", "
            div_charts[chart_name]["houses"][h_idx] += lbl

        # Seed Ascendant into every divisional chart
        for chart_name, a_sign in asc_map.items():
            add_to_div(chart_name, a_sign, "As")

        # ── 9. Populate D1 + all divisionals for each planet ──────────────────
        for se_id, label, name in bodies:
            lon  = planet_degrees[label]
            sign = int(lon // 30)

            add_planet_d1(sign, label)

            # Divisional varga positions
            for v in vargas:
                add_to_div(f"D{v}", get_varga_sign(lon, v), label)

            # Sun chart and Moon chart (D1 sign-wise mirror)
            add_to_div("Sun",  sign, label)
            add_to_div("Moon", sign, label)

            # Bhav Chalit — find which cusp range the planet falls in
            chalit_house = 0
            for i in range(12):
                h_start = chalit_houses[i]
                h_end   = chalit_houses[(i + 1) % 12]
                if h_start < h_end:
                    if h_start <= lon < h_end:   chalit_house = i
                else:                             # wraparound (e.g. 350° → 10°)
                    if lon >= h_start or lon < h_end: chalit_house = i
            add_to_div("Chalit", (asc_sign + chalit_house) % 12, label)

            # Ketu in all charts (mirrors Rahu's pass)
            if se_id == swe.TRUE_NODE:
                k_lon  = planet_degrees["Ke"]
                k_sign = int(k_lon // 30)
                add_planet_d1(k_sign, "Ke")

                for v in vargas:
                    add_to_div(f"D{v}", get_varga_sign(k_lon, v), "Ke")
                add_to_div("Sun",  k_sign, "Ke")
                add_to_div("Moon", k_sign, "Ke")

                k_chalit_house = 0
                for i in range(12):
                    h_start = chalit_houses[i]
                    h_end   = chalit_houses[(i + 1) % 12]
                    if h_start < h_end:
                        if h_start <= k_lon < h_end:           k_chalit_house = i
                    else:
                        if k_lon >= h_start or k_lon < h_end:  k_chalit_house = i
                add_to_div("Chalit", (asc_sign + k_chalit_house) % 12, "Ke")

        # ── 10. Ashtakvarga (SAV + individual BAVs) ───────────────────────────
        sav_raw = [0] * 12
        bav_map = {}

        for target_planet, contributions in ASHTAKVARGA_RULES.items():
            bav = [0] * 12
            for ref_body, offsets in contributions.items():
                ref_sign = planetary_signs.get(ref_body)
                if ref_sign is None:
                    continue
                for offset in offsets:
                    idx = (ref_sign + offset) % 12
                    bav[idx]     += 1
                    sav_raw[idx] += 1
            bav_map[target_planet] = {str(i): score for i, score in enumerate(bav)}

        # KEY FIX: use "SAV (Total)" to match Flutter's _kAshtakPlanets constant
        bav_map["SAV (Total)"] = {str(i): score for i, score in enumerate(sav_raw)}

        # ── 11. Panchang ──────────────────────────────────────────────────────
        tithi_diff = (moon_lon - sun_lon) % 360
        tithi_idx  = int(tithi_diff // 12)
        nak_idx    = int(moon_lon // (360 / 27))

        # ── 12. KP Planets ────────────────────────────────────────────────────
        kp_body_map = [
            ("Ascendant", asc_deg),
            ("Sun",       planet_degrees["Su"]),
            ("Moon",      planet_degrees["Mo"]),
            ("Mars",      planet_degrees["Ma"]),
            ("Mercury",   planet_degrees["Me"]),
            ("Jupiter",   planet_degrees["Ju"]),
            ("Venus",     planet_degrees["Ve"]),
            ("Saturn",    planet_degrees["Sa"]),
            ("Rahu",      planet_degrees["Ra"]),
            ("Ketu",      planet_degrees["Ke"]),
        ]
        kp_planets_out = []
        for p_name, p_deg in kp_body_map:
            sl, stl, subl = get_kp_lords(p_deg)
            kp_planets_out.append({
                "Planet":     p_name,
                "Sign Lord":  sl,
                "Star Lord":  stl,
                "Sub Lord":   subl,
            })

        # ── 13. KP Cusps (tropical → sidereal) ───────────────────────────────
        kp_cusps_out = []
        for i in range(12):
            c_deg_sid  = (houses[i] - ayanamsa) % 360
            sign_name  = ZODIAC_SIGNS[int(c_deg_sid / 30) % 12]
            sl, stl, subl = get_kp_lords(c_deg_sid)
            deg_part   = int(c_deg_sid)
            min_part   = int((c_deg_sid % 1) * 60)
            kp_cusps_out.append({
                "Cusp":       str(i + 1),
                "Degree":     f"{deg_part}°{min_part}'",
                "Sign":       sign_name,
                "Sign Lord":  sl,
                "Star Lord":  stl,
                "Sub Lord":   subl,
            })

        # ── 14. KP Ruling Planets ─────────────────────────────────────────────
        day_lords      = ["Moon","Mars","Mercury","Jupiter","Venus","Saturn","Sun"]
        weekday        = datetime(year, month, day).weekday()
        kp_ruling_out  = [
            {"Type": "Ascendant", "Sign Lord": kp_planets_out[0]["Sign Lord"], "Star Lord": kp_planets_out[0]["Star Lord"], "Sub Lord": kp_planets_out[0]["Sub Lord"]},
            {"Type": "Moon",      "Sign Lord": kp_planets_out[2]["Sign Lord"], "Star Lord": kp_planets_out[2]["Star Lord"], "Sub Lord": kp_planets_out[2]["Sub Lord"]},
            {"Type": "Day Lord",  "Sign Lord": day_lords[weekday],             "Star Lord": "-",                           "Sub Lord": "-"},
        ]

        # ── 15. Return ─────────────────────────────────────────────────────────
        return {
            "success":          True,
            "ayanamsha_used":   requested_ayanamsha,   # echo back for Flutter debug
            "ayanamsha_value":  round(ayanamsa, 6),    # actual degrees value
            "kundali_data": {
                "sun_sign":       ZODIAC_SIGNS[sun_sign],
                "moon_sign":      ZODIAC_SIGNS[moon_sign],
                "ascendant_sign": ZODIAC_SIGNS[asc_sign],
                "nakshatra":      NAKSHATRAS[nak_idx],
                "tithi":          TITHIS[tithi_idx],
            },
            "chart_houses":       chart_houses,
            "chart_signs":        chart_signs,
            "divisionals":        div_charts,
            "ashtakvarga_scores": bav_map,
            "planet_details":     planet_details_out,
            "kp_planets":         kp_planets_out,
            "kp_cusps":           kp_cusps_out,
            "kp_ruling":          kp_ruling_out,
            "dashas":             [],
        }

    except Exception as e:
        # Always return the actual error string so Flutter SnackBar can show it.
        # The generic "Python Server Error" with no detail was making debugging blind.
        import traceback
        return {
            "success": False,
            "error":   str(e),
            "trace":   traceback.format_exc(),   # remove this line in production if desired
        }

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
def read_root():
    return {"status": "TaaraVaani Engine is Online"}

@app.get("/api/version")
def get_version():
    """
    Returns the live pyswisseph version installed on this server.
    Hit this endpoint first when debugging ayanamsha constant errors —
    if the version is below 2.x, SIDM_TRUE_CITRA (ID 27) may not be available.
    """
    return {
        "pyswisseph_version": swe.__version__,
        "available_ayanamshas": list(AYANAMSHA_MAP.keys()),
        "default_ayanamsha":    DEFAULT_AYANAMSHA,
    }
@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"status": "ok"}
