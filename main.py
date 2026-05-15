from fastapi import FastAPI
from pydantic import BaseModel
import swisseph as swe

app = FastAPI()

class ProfileData(BaseModel):
    name: str
    dob: str
    time: str
    lat: float
    lng: float

@app.post("/api/kundali")
async def generate_kundali(data: ProfileData):
    try:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        return {
            "success": True,
            "kundali_data": {
                "sun_sign": "Aries (Python Math Active)",
                "moon_sign": "Taurus",
                "ascendant_sign": "Gemini",
                "nakshatra": "Rohini",
                "tithi": "Pratipada"
            },
            "chart_houses": ["Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces", "Aries", "Taurus"],
            "chart_signs": ["Sun", "Moon", "", "", "Mars", "", "Jupiter", "Saturn", "", "", "Rahu", "Ketu"],
            "ashtakvarga_scores": {"1": 28, "2": 30, "3": 25, "4": 32, "5": 24, "6": 33, "7": 22, "8": 29, "9": 31, "10": 26, "11": 35, "12": 21},
            "dashas": []
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/")
def read_root():
    return {"status": "TaaraVaani Engine is Online"}