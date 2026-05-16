from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # 🚨 ADDED THIS
from pydantic import BaseModel
from datetime import datetime
import swisseph as swe
from timezonefinder import TimezoneFinder
import pytz

app = FastAPI()

# 🚨 ADDED CORS MIDDLEWARE TO ALLOW FLUTTER WEB TO CONNECT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

tf = TimezoneFinder()
# ... rest of the code stays exactly the same

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
        
        # 🚨 THE TWEAK: Western Ascendant - Ayanamsa = Vedic Ascendant
       from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # 🚨 ADDED THIS
from pydantic import BaseModel
from datetime import datetime
import swisseph as swe
from timezonefinder import TimezoneFinder
import pytz

app = FastAPI()

# 🚨 ADDED CORS MIDDLEWARE TO ALLOW FLUTTER WEB TO CONNECT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

tf = TimezoneFinder()
# ... rest of the code stays exactly the same

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
        
        # 🚨 THE TWEAK: Western Ascendant - Ayanamsa = Vedic Ascendant
        # Switch to plain houses() which returns tropical, then subtract manually
        houses, ascmc = swe.houses_ex(julday, data.lat, data.lng, b'P')  # No FLG_SIDEREAL
        asc_deg = (ascmc[0] - ayanamsa) % 360  # Manual correction — same as Streamlit
        asc_sign = int(asc_deg // 30)

        chart_houses = [""] * 12
        chart_signs = [""] * 12
        planetary_signs = {"Asc": asc_sign}
        
        def add_planet(sign_idx, label):
            house_idx = (sign_idx - asc_sign) % 12
            if chart_houses[house_idx]: chart_houses[house_idx] += ", "
            chart_houses[house_idx] += label
            if chart_signs[sign_idx]: chart_signs[sign_idx] += ", "
            chart_signs[sign_idx] += label

        add_planet(asc_sign, "As")

        bodies = [
            (swe.SUN, 'Su', 'Sun'), (swe.MOON, 'Mo', 'Moon'), (swe.MARS, 'Ma', 'Mars'),
            (swe.MERCURY, 'Me', 'Mercury'), (swe.JUPITER, 'Ju', 'Jupiter'), 
            (swe.VENUS, 'Ve', 'Venus'), (swe.SATURN, 'Sa', 'Saturn'), (swe.TRUE_NODE, 'Ra', 'Rahu')
        ]

        sun_lon = 0
        moon_lon = 0

        for se_id, label, name in bodies:
            res, _ = swe.calc_ut(julday, se_id, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)
            lon = (res[0]) % 360
            
            if se_id == swe.SUN: sun_lon = lon
            if se_id == swe.MOON: moon_lon = lon
            
            sign = int(lon // 30)
            if se_id != swe.TRUE_NODE:
                planetary_signs[name] = sign
                
            add_planet(sign, label)
            
            if se_id == swe.TRUE_NODE:
                ketu_lon = (lon + 180) % 360
                ketu_sign = int(ketu_lon // 30)
                add_planet(ketu_sign, "Ke")

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

        return {
            "success": True,
            "kundali_data": {
                "sun_sign": ZODIAC_SIGNS[int(sun_lon // 30)],
                "moon_sign": ZODIAC_SIGNS[int(moon_lon // 30)],
                "ascendant_sign": ZODIAC_SIGNS[asc_sign],
                "nakshatra": NAKSHATRAS[nak_idx],
                "tithi": TITHIS[tithi_idx]
            },
            "chart_houses": chart_houses,
            "chart_signs": chart_signs,
            "ashtakvarga_scores": ashtakvarga_scores,
            "dashas": []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/")
def read_root():
    return {"status": "TaaraVaani Engine is Online"}
        asc_sign = int(asc_deg // 30)

        chart_houses = [""] * 12
        chart_signs = [""] * 12
        planetary_signs = {"Asc": asc_sign}
        
        def add_planet(sign_idx, label):
            house_idx = (sign_idx - asc_sign) % 12
            if chart_houses[house_idx]: chart_houses[house_idx] += ", "
            chart_houses[house_idx] += label
            if chart_signs[sign_idx]: chart_signs[sign_idx] += ", "
            chart_signs[sign_idx] += label

        add_planet(asc_sign, "As")

        bodies = [
            (swe.SUN, 'Su', 'Sun'), (swe.MOON, 'Mo', 'Moon'), (swe.MARS, 'Ma', 'Mars'),
            (swe.MERCURY, 'Me', 'Mercury'), (swe.JUPITER, 'Ju', 'Jupiter'), 
            (swe.VENUS, 'Ve', 'Venus'), (swe.SATURN, 'Sa', 'Saturn'), (swe.TRUE_NODE, 'Ra', 'Rahu')
        ]

        sun_lon = 0
        moon_lon = 0

        for se_id, label, name in bodies:
            res, _ = swe.calc_ut(julday, se_id, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)
            lon = (res[0]) % 360
            
            if se_id == swe.SUN: sun_lon = lon
            if se_id == swe.MOON: moon_lon = lon
            
            sign = int(lon // 30)
            if se_id != swe.TRUE_NODE:
                planetary_signs[name] = sign
                
            add_planet(sign, label)
            
            if se_id == swe.TRUE_NODE:
                ketu_lon = (lon + 180) % 360
                ketu_sign = int(ketu_lon // 30)
                add_planet(ketu_sign, "Ke")

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

        return {
            "success": True,
            "kundali_data": {
                "sun_sign": ZODIAC_SIGNS[int(sun_lon // 30)],
                "moon_sign": ZODIAC_SIGNS[int(moon_lon // 30)],
                "ascendant_sign": ZODIAC_SIGNS[asc_sign],
                "nakshatra": NAKSHATRAS[nak_idx],
                "tithi": TITHIS[tithi_idx]
            },
            "chart_houses": chart_houses,
            "chart_signs": chart_signs,
            "ashtakvarga_scores": ashtakvarga_scores,
            "dashas": []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/")
def read_root():
    return {"status": "TaaraVaani Engine is Online"}
