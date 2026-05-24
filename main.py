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
from datetime import datetime, timedelta
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

# ── Swiss Ephemeris File Path ─────────────────────────────────────────────────
# FIX 1: Always call set_ephe_path() at startup.
# True Citra (ID 27) is a DYNAMIC ayanamsha — it calls fixstar_ut("Spica", jd)
# internally to find Spica's true ecliptic longitude. This requires sefstars.txt
# (the fixed star catalog) and ideally the .se1 planetary data files.
# Without set_ephe_path(), pyswisseph cannot find these files on the server's
# filesystem, the internal star lookup silently corrupts the JD reference to ~0
# (JD 4713 BCE), and calc_ut() throws "outside Moshier planet range 625000..2818000".
# Lahiri (ID 1) never needed this because it uses the Newcomb formula only.
#
# To deploy: copy sefstars.txt (and optionally sepl*.se1, semo*.se1) into the
# directory pointed to by SWE_EPHE_PATH.  The star catalog alone (14 KB) is
# sufficient to unlock True Citra.  Full .se1 files give better precision but
# are not required.
import os
_EPHE_PATH = os.environ.get("SWE_EPHE_PATH", "/app/ephe")
swe.set_ephe_path(_EPHE_PATH)

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
    "kp":         5,    # 🚨 ADDED: Krishnamurti Paddhati Ayanamsha
    "true_citra": 27,   # True Chitrapaksha — requires sefstars.txt in ephe path
}
DEFAULT_AYANAMSHA = "true_citra"

# ── True Citra Availability Probe ─────────────────────────────────────────────
# FIX 2: Probe at startup whether ID 27 works on this build+environment.
# If True Citra is unavailable (missing catalog files or old pyswisseph),
# we fall back to Lahiri automatically so the server never returns a JD error
# to Flutter.  The ayanamsha_used field in the response tells Flutter which
# ayanamsha was actually applied.
def _probe_true_citra() -> bool:
    """Returns True only if SIDM_TRUE_CITRA (27) produces a sane ayanamsha at J2000.0."""
    try:
        swe.set_sid_mode(27)
        val = swe.get_ayanamsa_ut(2451545.0)   # J2000.0 — well inside any valid range
        return 20.0 < val < 30.0               # sane ayanamsha is ~23–24° right now
    except Exception:
        return False
    finally:
        swe.set_sid_mode(1)   # reset to Lahiri so the server starts clean

_TRUE_CITRA_AVAILABLE: bool = _probe_true_citra()

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

# ── Avakhada Chakra & Panchang Tables ─────────────────────────────────────────
YOGAS = ["Vishkumbha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma", "Dhriti", "Shoola", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"]
YONIS = ["Ashwa", "Gaja", "Aja", "Sarp", "Sarp", "Shwan", "Marjar", "Mesh", "Marjar", "Mushak", "Mushak", "Gau", "Mahish", "Vyaghr", "Mahish", "Vyaghr", "Mrig", "Mrig", "Shwan", "Kapi", "Nakul", "Kapi", "Simha", "Ashwa", "Gau", "Gau", "Gaja"]
GANS = ["Deva", "Manush", "Rakshas", "Manush", "Deva", "Rakshas", "Deva", "Deva", "Rakshas", "Rakshas", "Manush", "Manush", "Deva", "Rakshas", "Deva", "Rakshas", "Deva", "Rakshas", "Rakshas", "Manush", "Manush", "Deva", "Rakshas", "Rakshas", "Manush", "Manush", "Deva"]
NADIS = ["Aadi", "Madhya", "Antya", "Antya", "Madhya", "Aadi", "Aadi", "Madhya", "Antya", "Antya", "Madhya", "Aadi", "Aadi", "Madhya", "Antya", "Antya", "Madhya", "Aadi", "Aadi", "Madhya", "Antya", "Antya", "Madhya", "Aadi", "Aadi", "Madhya", "Antya"]
LETTERS = ["Chu","Che","Cho","La","Li","Lu","Le","Lo","A","I","U","E","O","Va","Vi","Vu","Ve","Vo","Ka","Ki","Ku","Gha","Ng","Chh","Ke","Ko","Ha","Hi","Hu","He","Ho","Da","Di","Du","De","Do","Ma","Mi","Mu","Me","Mo","Ta","Ti","Tu","Te","To","Pa","Pi","Pu","Sha","Na","Tha","Pe","Po","Ra","Ri","Ru","Re","Ro","Ta","Ti","Tu","Te","To","Na","Ni","Nu","Ne","No","Ya","Yi","Yu","Ye","Yo","Bha","Bhi","Bhu","Dha","Bha","Dha","Bhe","Bho","Ja","Ji","Ju","Je","Jo","Gha","Ga","Gi","Gu","Ge","Go","Sa","Si","Su","Se","So","Da","Di","Du","Tha","Jha","Jna","De","Do","Cha","Chi"]

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

        # Guard: reject missing or malformed dob/time before touching Swiss Ephemeris
        if not data.dob or not data.time or data.dob.strip() == '' or data.time.strip() == '':
            return {
                "success": False,
                "error": f"Missing birth data — dob='{data.dob}' time='{data.time}'. Profile is incomplete in the database."
            }

        year, month, day          = map(int, data.dob.strip().split('-'))
        hour, minute, sec         = map(int, (data.time.strip() + ':00').split(':')[:3])

        local_dt = local_tz.localize(datetime(year, month, day, hour, minute, sec))
        utc_dt   = local_dt.astimezone(pytz.utc)

        # ── 2. Set Ayanamsha (ALWAYS use integer ID — never swe.SIDM_* constant) ──
        # swe.SIDM_* named constants were added at different pyswisseph versions.
        # Using the integer directly works on every pyswisseph build from 1.x onward.
        requested_ayanamsha = (data.ayanamsha or DEFAULT_AYANAMSHA).lower().strip()

        # FIX 3a: Fall back to Lahiri if True Citra is not available.
        # True Citra needs sefstars.txt in the ephemeris path.  The startup probe
        # (_TRUE_CITRA_AVAILABLE) verified this once at boot so we don't repeat
        # the star lookup on every request.
        if requested_ayanamsha == "true_citra" and not _TRUE_CITRA_AVAILABLE:
            requested_ayanamsha = "lahiri"
            # Note: ayanamsha_used in the response will reflect the actual fallback

        sid_mode_id = AYANAMSHA_MAP.get(requested_ayanamsha, AYANAMSHA_MAP[DEFAULT_AYANAMSHA])
        swe.set_sid_mode(sid_mode_id)   # ← must be called before any swe calculation

        # ── 3. Julian Day ─────────────────────────────────────────────────────
        julday   = swe.julday(
            utc_dt.year, utc_dt.month, utc_dt.day,
            utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
        )

        # FIX 3b: JD sanity guard — Moshier range is 625000–2818000 (≈1800 BCE–3000 CE).
        # A JD near 0 means the date/time parsing or timezone conversion has gone wrong.
        # Catching this here gives a readable error instead of the cryptic range message.
        if not (625000 < julday < 2818000):
            return {
                "success": False,
                "error": (
                    f"Computed Julian Day {julday:.3f} is outside the supported ephemeris "
                    f"range (625000–2818000, i.e. 1800 BCE–3000 CE). "
                    f"Check that dob='{data.dob}' and time='{data.time}' are valid and "
                    f"that the timezone resolved correctly (tz='{tz_str}')."
                ),
            }

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

    
        # FLG_SPEED gives us the daily motion — negative = retrograde.
        CALC_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED

        planet_degrees   = {}
        planet_details_out = []
        planetary_signs  = {"Asc": asc_sign}
        sun_lon = moon_lon = 0.0

        for se_id, label, name in bodies:
            res, _  = swe.calc_ut(julday, se_id, CALC_FLAGS)
            lon     = (res[0] - ayanamsa) % 360          # sidereal longitude 0–360°
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

        # ── 11. Extended Panchang & Avakhada Chakra ───────────────────────────
        tithi_diff = (moon_lon - sun_lon) % 360
        tithi_idx  = int(tithi_diff // 12)
        nak_idx    = int(moon_lon // (360 / 27))
        charan     = int((moon_lon % (360 / 27)) / (360 / 108)) + 1
        yoga_idx   = int((sun_lon + moon_lon) // (13 + 20/60)) % 27
        
        # Karan Calculation
        karan_val = int(tithi_diff // 6)
        if karan_val == 0: karan_name = "Kintughna"
        elif karan_val == 57: karan_name = "Shakuni"
        elif karan_val == 58: karan_name = "Chatushpada"
        elif karan_val == 59: karan_name = "Naga"
        else: karan_name = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"][(karan_val - 1) % 7]

        # Sunrise & Sunset (Swiss Ephemeris exact calculation)
        sunrise_str, sunset_str = "06:00:00", "18:00:00"
        try:
            res_rise = swe.rise_trans(julday, swe.SUN, b'', swe.CALC_RISE, (data.lng, data.lat, 0.0), 0, 0)
            res_set  = swe.rise_trans(julday, swe.SUN, b'', swe.CALC_SET,  (data.lng, data.lat, 0.0), 0, 0)
            def jd_to_local(jd):
                y, m, d, h = swe.revjul(jd)
                dt = datetime(y, m, d, int(h), int((h - int(h)) * 60), int((((h - int(h)) * 60) - int((h - int(h)) * 60)) * 60), tzinfo=pytz.utc)
                return dt.astimezone(local_tz).strftime('%H:%M:%S')
            sunrise_str = jd_to_local(res_rise[0][0])
            sunset_str  = jd_to_local(res_set[0][0])
        except Exception: pass

        avakhada_out = {
            "Varna": ["Kshattriya", "Vaishya", "Shudra", "Brahmin"][moon_sign % 4],
            "Vashya": ["Chatushpada", "Chatushpada", "Dwipada", "Jalchar", "Vanchar", "Dwipada", "Dwipada", "Keet", "Chatushpada", "Chatushpada", "Dwipada", "Jalchar"][moon_sign],
            "Yoni": YONIS[nak_idx],
            "Gan": GANS[nak_idx],
            "Nadi": NADIS[nak_idx],
            "Sign": ZODIAC_SIGNS[moon_sign],
            "Sign Lord": SIGN_LORDS[moon_sign],
            "Nakshatra-Charan": f"{NAKSHATRAS[nak_idx]} - {charan}",
            "Yog": YOGAS[yoga_idx],
            "Karan": karan_name,
            "Tithi": TITHIS[tithi_idx],
            "Yunja": "Poorva",
            "Tatva": ["Fire", "Earth", "Air", "Water"][moon_sign % 4],
            "Name Alphabet": LETTERS[int(moon_lon // (360/108))],
            "Paya": ["Gold", "Iron", "Copper", "Silver"][nak_idx % 4]
        }

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

        # ── 15. Vimshottari & Yogini Dasha Engine (Time Travel Math) ──────────
    
        
        birth_dt = datetime(year, month, day)
        nak_width = 360 / 27
        passed_nak = moon_lon % nak_width
        elapsed_ratio = passed_nak / nak_width
        
        # 15A. Vimshottari Dasha (6 Levels Unleashed)
        VIM_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
        VIM_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
        start_vim_idx = nak_idx % 9
        vim_elapsed_days = VIM_YEARS[start_vim_idx] * elapsed_ratio * 365.2425
        vim_hypo_start = birth_dt - timedelta(days=vim_elapsed_days)
        
        # ARCHITECTURE — Lazy-Load Dasha Engine
        # Levels 1–4 pre-computed here  →  6,561 nodes  →  safe on 512 MB RAM
        # Levels 5–6 (Prana, Deha)       →  fetched on-tap via /api/dasha/sublevel
        #
        # Every node carries lord_idx + duration_years so Flutter can reconstruct
        # any sub-level without extra round-trips to the main endpoint.
        # has_sub=True signals Flutter to show an expand arrow even when sub_dashas=[].
        def calc_vim(start_dt, lord_idx, duration_years, current_lvl, max_lvl):
            nodes = []
            curr_dt = start_dt
            for i in range(9):
                sub_idx      = (lord_idx + i) % 9
                sub_duration = duration_years * (VIM_YEARS[sub_idx] / 120.0)
                sub_days     = sub_duration * 365.2425
                end_dt       = curr_dt + timedelta(days=sub_days)
                node = {
                    "lord":           VIM_LORDS[sub_idx],
                    "start":          curr_dt.strftime("%d %b %Y"),
                    "end":            end_dt.strftime("%d %b %Y"),
                    "lord_idx":       sub_idx,
                    "duration_years": sub_duration,
                    "has_sub":        True,   # levels 5+6 always exist
                }
                if current_lvl < max_lvl:
                    node["sub_dashas"] = calc_vim(curr_dt, sub_idx, sub_duration, current_lvl + 1, max_lvl)
                nodes.append(node)
                curr_dt = end_dt
            return nodes

        vimshottari_dashas = []
        curr_v_dt = vim_hypo_start
        for i in range(9):
            md_idx  = (start_vim_idx + i) % 9
            md_years = VIM_YEARS[md_idx]
            md_days  = md_years * 365.2425
            end_dt   = curr_v_dt + timedelta(days=md_days)
            vimshottari_dashas.append({
                "lord":           VIM_LORDS[md_idx],
                "start":          curr_v_dt.strftime("%d %b %Y"),
                "end":            end_dt.strftime("%d %b %Y"),
                "lord_idx":       md_idx,
                "duration_years": float(md_years),
                "has_sub":        True,
                # Pre-load levels 2–4 (Antar, Pratyantar, Sookshma) — 6,561 nodes max.
                # Levels 5 (Prana) and 6 (Deha) are fetched lazily on user tap.
                "sub_dashas": calc_vim(curr_v_dt, md_idx, md_years, 2, 4)
            })
            curr_v_dt = end_dt

        # 15B. Yogini Dasha (4 Levels)
        YOGINI_NAMES = ["Sankata", "Mangala", "Pingala", "Dhanya", "Bhramari", "Bhadrika", "Ulka", "Siddha"]
        YOGINI_YEARS = [8, 1, 2, 3, 4, 5, 6, 7]
        start_yog_idx = ((nak_idx + 1) + 3) % 8
        yog_elapsed_days = YOGINI_YEARS[start_yog_idx] * elapsed_ratio * 365.2425
        yog_hypo_start = birth_dt - timedelta(days=yog_elapsed_days)

        def calc_yog(start_dt, lord_idx, duration_years, current_lvl, max_lvl):
            nodes = []
            curr_dt = start_dt
            for i in range(8):
                sub_idx = (lord_idx + i) % 8
                sub_duration = duration_years * (YOGINI_YEARS[sub_idx] / 36.0)
                sub_days = sub_duration * 365.2425
                end_dt = curr_dt + timedelta(days=sub_days)
                node = {
                    "lord": YOGINI_NAMES[sub_idx],
                    "start": curr_dt.strftime("%d %b %Y"),
                    "end": end_dt.strftime("%d %b %Y"),
                }
                if current_lvl < max_lvl:
                    node["sub_dashas"] = calc_yog(curr_dt, sub_idx, sub_duration, current_lvl + 1, max_lvl)
                nodes.append(node)
                curr_dt = end_dt
            return nodes

        yogini_dashas = []
        curr_y_dt = yog_hypo_start
        for cycle in range(3): # Generate 3 cycles to cover 108 years of life
            for i in range(8):
                md_idx = (start_yog_idx + i) % 8
                md_years = YOGINI_YEARS[md_idx]
                md_days = md_years * 365.2425
                end_dt = curr_y_dt + timedelta(days=md_days)
                yogini_dashas.append({
                    "lord": YOGINI_NAMES[md_idx],
                    "start": curr_y_dt.strftime("%d %b %Y"),
                    "end": end_dt.strftime("%d %b %Y"),
                    "sub_dashas": calc_yog(curr_y_dt, md_idx, md_years, 2, 4)
                })
                curr_y_dt = end_dt # 🚨 FIXED INDENTATION

        # ── 15.5 Dosha & Sadesati Math Engine (100-Year Orbital Scanner) ──────
        mars_sign = int(planet_degrees["Ma"] // 30)
        mars_house = ((mars_sign - asc_sign) % 12) + 1
        is_manglik = mars_house in [1, 4, 7, 8, 12]
        manglik_reasons = [f"Mars is positioned in the {mars_house}th house from the Ascendant."] if is_manglik else []

        rahu_lon = planet_degrees["Ra"]
        lons = [(planet_degrees[p] - rahu_lon) % 360 for p in ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa"]]
        is_kalsarpa = all(0 < l < 180 for l in lons) or all(180 < l < 360 for l in lons)

        ss_rising = (moon_sign - 1) % 12
        ss_peak = moon_sign
        ss_setting = (moon_sign + 1) % 12
        target_ss_signs = {ss_rising: "Rising", ss_peak: "Peak", ss_setting: "Setting"}

        sadesati_periods = []
        scan_jd = julday - (5 * 365.25)
        end_scan_jd = julday + (90 * 365.25)
        
        current_ss_sign = None
        start_transit_jd = None
        
        while scan_jd < end_scan_jd:
            swe.set_sid_mode(sid_mode_id)
            res_sat, _ = swe.calc_ut(scan_jd, swe.SATURN, CALC_FLAGS)
            sat_sign = int(((res_sat[0] - swe.get_ayanamsa_ut(scan_jd)) % 360) // 30)

            if sat_sign in target_ss_signs:
                if current_ss_sign is None:
                    current_ss_sign = sat_sign
                    start_transit_jd = scan_jd
                elif sat_sign != current_ss_sign:
                    y1, m1, d1, _ = swe.revjul(start_transit_jd)
                    y2, m2, d2, _ = swe.revjul(scan_jd)
                    sadesati_periods.append({
                        "start": datetime(y1, m1, d1).strftime("%d %b %Y"),
                        "end": datetime(y2, m2, d2).strftime("%d %b %Y"),
                        "sign": ZODIAC_SIGNS[current_ss_sign],
                        "type": target_ss_signs[current_ss_sign]
                    })
                    current_ss_sign = sat_sign
                    start_transit_jd = scan_jd
            else:
                if current_ss_sign is not None:
                    y1, m1, d1, _ = swe.revjul(start_transit_jd)
                    y2, m2, d2, _ = swe.revjul(scan_jd)
                    sadesati_periods.append({
                        "start": datetime(y1, m1, d1).strftime("%d %b %Y"),
                        "end": datetime(y2, m2, d2).strftime("%d %b %Y"),
                        "sign": ZODIAC_SIGNS[current_ss_sign],
                        "type": target_ss_signs[current_ss_sign]
                    })
                    current_ss_sign = None
                    start_transit_jd = None
            scan_jd += 5.0 

        now_dt = datetime.utcnow()
        now_jd = swe.julday(now_dt.year, now_dt.month, now_dt.day, 12.0)
        res_now, _ = swe.calc_ut(now_jd, swe.SATURN, CALC_FLAGS)
        sat_now_sign = int(((res_now[0] - swe.get_ayanamsa_ut(now_jd)) % 360) // 30)
        
        is_ss_active = sat_now_sign in target_ss_signs
        current_ss_phase = target_ss_signs.get(sat_now_sign, "Rising")
        current_ss_from = ""
        current_ss_to = ""

        if is_ss_active:
            for p in sadesati_periods:
                try:
                    s_dt = datetime.strptime(p['start'], "%d %b %Y")
                    e_dt = datetime.strptime(p['end'], "%d %b %Y")
                    if s_dt <= now_dt <= e_dt:
                        current_ss_from = p['start']
                        current_ss_to = p['end']
                        break
                except: pass

        # ── 16. Return (🚨 FIXED: NO DUPLICATE KEYS) ───────────────────────────
        return {
            "success":          True,
            "ayanamsha_used":   requested_ayanamsha,
            "ayanamsha_value":  round(ayanamsa, 6),
            "kundali_data": {
                "sun_sign":       ZODIAC_SIGNS[sun_sign],
                "moon_sign":      ZODIAC_SIGNS[moon_sign],
                "ascendant_sign": ZODIAC_SIGNS[asc_sign],
                "nakshatra":      NAKSHATRAS[nak_idx],
                "tithi":          TITHIS[tithi_idx],
                "sunrise":        sunrise_str,
                "sunset":         sunset_str,
                "karan":          karan_name,
                "yog":            YOGAS[yoga_idx],
                "avakhada":       avakhada_out,
                "manglik":                is_manglik,
                "manglik_reasons":        manglik_reasons,
                "kalsarpa":               is_kalsarpa,
                "sadesati_active":        is_ss_active,
                "sadesati_current_phase": current_ss_phase,
                "sadesati_current_from":  current_ss_from,
                "sadesati_current_to":    current_ss_to,
                "sadesati_periods":       sadesati_periods,
            },
            "chart_houses":       chart_houses,
            "chart_signs":        chart_signs,
            "divisionals":        div_charts,
            "ashtakvarga_scores": bav_map,
            "planet_details":     planet_details_out,
            "kp_planets":         kp_planets_out,
            "kp_cusps":           kp_cusps_out,
            "kp_ruling":          kp_ruling_out,
            "dashas":             {"vimshottari": vimshottari_dashas, "yogini": yogini_dashas},
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

# ── Lazy Dasha Sub-Level Endpoint ────────────────────────────────────────────
# Flutter calls this when the user taps to expand Level 5 (Prana) or Level 6
# (Deha). Returns exactly 9 nodes — no recursion, no OOM risk.
#
# Request:  lord_idx (0-8), start_date ("DD Mon YYYY"), duration_years, level (5 or 6)
# Response: 9 child nodes, each carrying lord_idx + duration_years for further expansion
#
# Level 5 nodes have has_sub=True  (Deha children exist)
# Level 6 nodes have has_sub=False (Deha is the true leaf — nothing below)

class SubLevelRequest(BaseModel):
    lord_idx:       int
    start_date:     str    # "DD Mon YYYY" — same format the main endpoint returns
    duration_years: float
    level:          int    # 5 = computing Prana, 6 = computing Deha

@app.post("/api/dasha/sublevel")
async def get_dasha_sublevel(data: SubLevelRequest):
    try:
        VIM_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
        VIM_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]

        try:
            start_dt = datetime.strptime(data.start_date, "%d %b %Y")
        except ValueError:
            start_dt = datetime.strptime(data.start_date, "%Y-%m-%d")

        nodes    = []
        curr_dt  = start_dt
        for i in range(9):
            sub_idx      = (data.lord_idx + i) % 9
            sub_duration = data.duration_years * (VIM_YEARS[sub_idx] / 120.0)
            sub_days     = sub_duration * 365.2425
            end_dt       = curr_dt + timedelta(days=sub_days)
            nodes.append({
                "lord":           VIM_LORDS[sub_idx],
                "start":          curr_dt.strftime("%d %b %Y"),
                "end":            end_dt.strftime("%d %b %Y"),
                "lord_idx":       sub_idx,
                "duration_years": sub_duration,
                "has_sub":        data.level < 6,  # Prana(5) has Deha children; Deha(6) is leaf
            })
            curr_dt = end_dt

        return {"success": True, "level": data.level, "nodes": nodes}
    except Exception as e:
        return {"success": False, "error": str(e)}



@app.get("/api/version")
def get_version():
    """
    Returns the live pyswisseph version installed on this server.
    Hit this endpoint first when debugging ayanamsha constant errors —
    if the version is below 2.x, SIDM_TRUE_CITRA (ID 27) may not be available.
    Also reports true_citra_available so Flutter can warn the user proactively.
    """
    return {
        "pyswisseph_version":    swe.__version__,
        "ephe_path":             _EPHE_PATH,
        "true_citra_available":  _TRUE_CITRA_AVAILABLE,
        "available_ayanamshas":  list(AYANAMSHA_MAP.keys()),
        "default_ayanamsha":     DEFAULT_AYANAMSHA,
    }
@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"status": "ok"}
