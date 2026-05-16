from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

class ProfileData(BaseModel):
    name: str
    dob: str
    time: str
    lat: float
    lng: float

ASHTAKVARGA_RULES = {
    "Sun": {"Sun": [0, 1, 3, 6, 7, 8, 9, 10], "Moon": [2, 5, 9, 10], "Mars": [0, 1, 3, 6, 7, 8, 9, 10], "Mercury": [2, 4, 5, 8, 9, 10, 11], "Jupiter": [4, 5, 8, 10], "Venus": [5, 6, 11], "Saturn": [0, 1, 3, 6, 7, 8, 9, 10], "Asc": [2, 3, 5, 9, 10, 11]},
    "Moon": {"Sun": [2, 5, 6, 7, 9, 10], "Moon": [0, 2, 5, 6, 9, 10], "Mars": [1, 2, 4, 5, 8, 9, 10], "Mercury": [0, 2, 3, 4, 6, 7, 9, 10], "Jupiter": [0, 3, 6, 7, 9, 10, 11], "Venus": [2, 3, 4, 6, 8, 9, 10], "Saturn": [2, 4, 5, 10], "Asc": [2, 5, 9, 10]},
    "Mars": {"Sun": [2, 4, 5, 9, 10], "Moon": [2, 5, 10], "Mars": [0, 1, 3, 6, 7, 9, 10], "Mercury": [2, 4, 5, 10], "Jupiter": [5, 9, 10, 11], "Venus": [5, 7, 10, 11], "Saturn": [0, 3, 6, 7, 8, 9, 10], "Asc": [0, 2, 5, 9, 10]},
    "Mercury": {"Sun": [4, 5, 8, 10, 11], "Moon": [1, 3, 5, 7, 9, 10], "Mars": [0, 1, 3, 6, 7, 8, 9, 10], "Mercury": [0, 2, 4, 5, 8, 9, 10, 11], "Jupiter": [5, 7, 10, 11], "Venus": [0, 1, 2, 3, 4, 7, 8, 10], "Saturn": [0, 1, 3, 6, 7, 8, 9, 10], "Asc": [0, 1, 3, 5, 7, 9, 10]},
    "Jupiter": {"Sun": [0, 1, 2, 3, 6, 7, 8, 9, 10], "Moon": [1, 4, 6, 8, 10], "Mars": [0, 1, 3, 6, 7, 9, 10], "Mercury": [0, 1, 3, 4, 5, 8, 9, 10], "Jupiter": [0, 1, 2, 3, 6, 7, 9, 10], "Venus": [1, 4, 5, 8, 9, 10], "Saturn": [2, 4, 5, 11], "Asc": [0, 1, 3, 4, 5, 6, 8, 9, 10]},
    "Venus": {"Sun": [7, 10, 11], "Moon": [0, 1, 2, 3, 4, 7, 8, 10, 11], "Mars": [2, 4, 5, 8, 10, 11], "Mercury": [2, 4, 5, 8, 10], "Jupiter": [4, 7, 8, 9, 10], "Venus": [0, 1, 2, 3, 4, 7, 8, 9, 10], "Saturn": [2, 3, 4, 7, 8, 9, 10], "Asc": [0, 1, 2, 3, 4, 7, 8, 10]},
    "Saturn": {"Sun": [0, 1, 3, 6, 7, 9, 10], "Moon": [2, 5, 10], "Mars": [2, 4, 5, 9, 10, 11], "Mercury": [5, 7, 8, 9, 10, 11], "Jupiter": [4, 5, 10, 11], "Venus": [5, 10, 11], "Saturn": [2, 4, 5, 10], "Asc": [0, 2, 3, 5, 9, 10]}
}

TITHIS = ['Pratipada', 'Dwitiya', 'Tritiya', 'Chaturthi', 'Panchami', 'Shashthi', 'Saptami', 'Ashtami', 'Navami', 'Dashami', 'Ekadashi', 'Dwadashi', 'Trayodashi', 'Chaturdashi', 'Purnima', 'Pratipada (K)', 'Dwitiya (K)', 'Tritiya (K)', 'Chaturthi (K)', 'Panchami (K)', 'Shashthi (K)', 'Saptami (K)', 'Ashtami (K)', 'Navami (K)', 'Dashami (K)', 'Ekadashi (K)', 'Dwadashi (K)', 'Trayodashi (K)', 'Chaturdashi (K)', 'Amavasya']
NAKSHATRAS = ['Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashirsha', 'Ardra', 'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni', 'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha', 'Moola', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati']
ZODIAC_SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

def get_kp_lords(deg: float):
    """Returns (Sign Lord, Star Lord, Sub Lord) for a sidereal longitude."""
    lords      = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    years      = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    sign_lords = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
                  "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
    sign_lord  = sign_lords[int(deg / 30) % 12]
    nak_span   = 13 + (20 / 60)
    nak_idx    = int(deg / nak_span)
    star_lord  = lords[nak_idx % 9]
    deg_in_nak = deg - (nak_idx * nak_span)
    min_in_nak = deg_in_nak * 60
    curr, acc  = nak_idx % 9, 0.0
    sub_lord   = lords[curr]
    for _ in range(9):
        span = (years[curr] / 120) * 800
        if min_in_nak < acc + span:
            sub_lord = lords[curr]
            break
        acc += span
        curr = (curr + 1) % 9
    return sign_lord, star_lord, sub_lord

@app.post("/api/kundali")
async def generate_kundali(data: ProfileData):
    try:
        tz_str = tf.timezone_at(lng=data.lng, lat=data.lat) or 'Asia/Kolkata'
        local_tz = pytz.timezone(tz_str)
        
        year, month, day = map(int, data.dob.split('-'))
        hour, minute, sec = map(int, (data.time + ':00').split(':')[:3])
        
        local_dt = local_tz.localize(datetime(year, month, day, hour, minute, sec))
        utc_dt = local_dt.astimezone(pytz.utc)
        
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        julday = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0)
        
        ayanamsa = swe.get_ayanamsa_ut(julday)

        # D1 Lagna calculation
        houses, ascmc = swe.houses_ex(julday, data.lat, data.lng, b'P')
        asc_deg = (ascmc[0] - ayanamsa) % 360
        asc_sign = int(asc_deg // 30)

        # 🚨 MASTER VARGA ALGORITHM
        def get_varga_sign(degree, varga):
            sign = int(degree // 30)
            deg_in_sign = degree % 30
            if varga == 2:
                if sign % 2 == 0: return 4 if deg_in_sign < 15 else 3
                else: return 3 if deg_in_sign < 15 else 4
            elif varga == 3: return (sign + int(deg_in_sign // 10) * 4) % 12
            elif varga == 4: return (sign + int(deg_in_sign // 7.5) * 3) % 12
            elif varga == 7:
                start = sign if sign % 2 == 0 else (sign + 6) % 12
                return (start + int(deg_in_sign // (30/7))) % 12
            elif varga == 9: return int((degree * 9) // 30) % 12
            elif varga == 10:
                start = sign if sign % 2 == 0 else (sign + 8) % 12
                return (start + int(deg_in_sign // 3)) % 12
            elif varga == 12: return (sign + int(deg_in_sign // 2.5)) % 12
            elif varga == 16:
                mod3 = sign % 3
                start = 0 if mod3 == 0 else (4 if mod3 == 1 else 8)
                return (start + int(deg_in_sign // (30/16))) % 12
            elif varga == 20:
                mod3 = sign % 3
                start = 0 if mod3 == 0 else (8 if mod3 == 1 else 4)
                return (start + int(deg_in_sign // 1.5)) % 12
            elif varga == 24:
                start = 4 if sign % 2 == 0 else 3
                return (start + int(deg_in_sign // 1.25)) % 12
            elif varga == 27:
                mod4 = sign % 4
                start = 0 if mod4 == 0 else (3 if mod4 == 1 else (6 if mod4 == 2 else 9))
                return (start + int(deg_in_sign // (30/27))) % 12
            elif varga == 30:
                d = deg_in_sign
                if sign % 2 == 0:
                    if d < 5: return 0
                    elif d < 10: return 10
                    elif d < 18: return 8
                    elif d < 25: return 2
                    else: return 6
                else:
                    if d < 5: return 1
                    elif d < 12: return 5
                    elif d < 20: return 11
                    elif d < 25: return 9
                    else: return 7
            elif varga == 40:
                start = 0 if sign % 2 == 0 else 6
                return (start + int(deg_in_sign // 0.75)) % 12
            elif varga == 45:
                mod3 = sign % 3
                start = 0 if mod3 == 0 else (4 if mod3 == 1 else 8)
                return (start + int(deg_in_sign // (30/45))) % 12
            elif varga == 60: return (sign + int(deg_in_sign * 2)) % 12
            return sign

        vargas = [2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60]
        
        # 1. Fetch exact planetary longitudes
        sun_lon, moon_lon = 0, 0
        bodies = [
            (swe.SUN, 'Su', 'Sun'), (swe.MOON, 'Mo', 'Moon'), (swe.MARS, 'Ma', 'Mars'),
            (swe.MERCURY, 'Me', 'Mercury'), (swe.JUPITER, 'Ju', 'Jupiter'), 
            (swe.VENUS, 'Ve', 'Venus'), (swe.SATURN, 'Sa', 'Saturn'), (swe.TRUE_NODE, 'Ra', 'Rahu')
        ]
        planet_degrees = {}
        for se_id, label, name in bodies:
            res, _ = swe.calc_ut(julday, se_id, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)
            lon = (res[0]) % 360
            planet_degrees[label] = lon
            if se_id == swe.SUN: sun_lon = lon
            if se_id == swe.MOON: moon_lon = lon
        
        sun_sign = int(sun_lon // 30)
        moon_sign = int(moon_lon // 30)

        # 2. Map Ascendants for EVERY divisional chart (Lagna of that chart)
        asc_map = {f"D{v}": get_varga_sign(asc_deg, v) for v in vargas}
        asc_map["Sun"] = sun_sign
        asc_map["Moon"] = moon_sign
        asc_map["Chalit"] = asc_sign # Simplified Bhava Chalit

        # 3. Create arrays for Houses AND Signs for all Vargas
        div_charts = {k: {"signs": [""] * 12, "houses": [""] * 12} for k in asc_map.keys()}

        def add_to_div(chart_name, p_sign, label):
            a_sign = asc_map[chart_name]
            h_idx = (p_sign - a_sign) % 12 # Calculate House relative to the specific Varga's Lagna!
            if div_charts[chart_name]["signs"][p_sign]: div_charts[chart_name]["signs"][p_sign] += ", "
            div_charts[chart_name]["signs"][p_sign] += label
            if div_charts[chart_name]["houses"][h_idx]: div_charts[chart_name]["houses"][h_idx] += ", "
            div_charts[chart_name]["houses"][h_idx] += label

        # 4. Inject "As" (Ascendant) into all Varga charts
        for chart_name, a_sign in asc_map.items():
            add_to_div(chart_name, a_sign, "As")

        # Basic D1 Setup
        chart_houses = [""] * 12
        chart_signs = [""] * 12
        planetary_signs = {"Asc": asc_sign}

        def add_planet_d1(sign_idx, label):
            house_idx = (sign_idx - asc_sign) % 12
            if chart_houses[house_idx]: chart_houses[house_idx] += ", "
            chart_houses[house_idx] += label
            if chart_signs[sign_idx]: chart_signs[sign_idx] += ", "
            chart_signs[sign_idx] += label

        add_planet_d1(asc_sign, "As")

        # 5. Distribute planets into D1 and all Vargas
        for se_id, label, name in bodies:
            lon = planet_degrees[label]
            sign = int(lon // 30)
            if se_id != swe.TRUE_NODE: planetary_signs[name] = sign
            
            add_planet_d1(sign, label)
            
            # Distribute to Vargas
            for v in vargas:
                v_sign = get_varga_sign(lon, v)
                add_to_div(f"D{v}", v_sign, label)
            
            add_to_div("Sun", sign, label)
            add_to_div("Moon", sign, label)
            add_to_div("Chalit", sign, label)
            
            if se_id == swe.TRUE_NODE:
                k_lon = (lon + 180) % 360
                k_sign = int(k_lon // 30)
                add_planet_d1(k_sign, "Ke")
                for v in vargas:
                    v_sign = get_varga_sign(k_lon, v)
                    add_to_div(f"D{v}", v_sign, "Ke")
                add_to_div("Sun", k_sign, "Ke")
                add_to_div("Moon", k_sign, "Ke")
                add_to_div("Chalit", k_sign, "Ke")

        # SAV Calculation
        sav_raw = [0] * 12
        for target_planet, contributions in ASHTAKVARGA_RULES.items():
            for ref_body, offsets in contributions.items():
                ref_sign = planetary_signs.get(ref_body)
                if ref_sign is None: continue
                for offset in offsets:
                    target_sign = (ref_sign + offset) % 12
                    sav_raw[target_sign] += 1
                    
        ashtakvarga_scores = {str(i): score for i, score in enumerate(sav_raw)}

        tithi_diff = (moon_lon - sun_lon) % 360
        tithi_idx = int(tithi_diff // 12)
        nak_idx = int(moon_lon // (360/27))

        # ── KP Planets ────────────────────────────────────────────────────────────
        ketu_lon = (planet_degrees["Ra"] + 180) % 360
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
            ("Ketu",      ketu_lon),
        ]
        kp_planets_out = []
        for p_name, p_deg in kp_body_map:
            sl, stl, subl = get_kp_lords(p_deg)
            kp_planets_out.append({"Planet": p_name, "Sign Lord": sl, "Star Lord": stl, "Sub Lord": subl})

        # ── KP Cusps (tropical house cusps → sidereal via ayanamsa) ──────────────
        kp_cusps_out = []
        for i in range(12):
            c_deg_sid = (houses[i] - ayanamsa) % 360
            sign_name = ZODIAC_SIGNS[int(c_deg_sid / 30) % 12]
            d_in_sign = c_deg_sid % 30
            sl, stl, subl = get_kp_lords(c_deg_sid)
            kp_cusps_out.append({
                "Cusp":      str(i + 1),
                "Degree":    f"{int(d_in_sign)}°{int((d_in_sign % 1) * 60)}'",
                "Sign":      sign_name,
                "Sign Lord": sl,
                "Star Lord": stl,
                "Sub Lord":  subl,
            })

        # ── Ruling Planets ────────────────────────────────────────────────────────
        day_lords = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]
        weekday   = datetime(year, month, day).weekday()
        kp_ruling_out = [
            {"Type": "Ascendant", "Sign Lord": kp_planets_out[0]["Sign Lord"], "Star Lord": kp_planets_out[0]["Star Lord"], "Sub Lord": kp_planets_out[0]["Sub Lord"]},
            {"Type": "Moon",      "Sign Lord": kp_planets_out[2]["Sign Lord"], "Star Lord": kp_planets_out[2]["Star Lord"], "Sub Lord": kp_planets_out[2]["Sub Lord"]},
            {"Type": "Day Lord",  "Sign Lord": day_lords[weekday],             "Star Lord": "-",                           "Sub Lord": "-"},
        ]

        return {
            "success": True,
            "kundali_data": {
                "sun_sign":       ZODIAC_SIGNS[int(sun_lon // 30)],
                "moon_sign":      ZODIAC_SIGNS[int(moon_lon // 30)],
                "ascendant_sign": ZODIAC_SIGNS[asc_sign],
                "nakshatra":      NAKSHATRAS[nak_idx],
                "tithi":          TITHIS[tithi_idx]
            },
            "chart_houses":       chart_houses,
            "chart_signs":        chart_signs,
            "divisionals":        div_charts,
            "ashtakvarga_scores": ashtakvarga_scores,
            "kp_planets":         kp_planets_out,
            "kp_cusps":           kp_cusps_out,
            "kp_ruling":          kp_ruling_out,
            "dashas":             []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/")
def read_root():
    return {"status": "TaaraVaani Engine is Online"}
