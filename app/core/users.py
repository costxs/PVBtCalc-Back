from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

HARDCODED_USERS = {
    "admin@valente":{
        "username": "Administrator",
        "hashad_password": pwd_context.hash("AdminTech")
    },
    "lcpetro":{
        "username":"LcPetro",
        "hashad_password": pwd_context.hash("pvbtcalc@2025"),
    }
}

def verify_user_password(plain_password: str, email: str) -> bool:
    user = HARDCODED_USERS.get(email)
    if not user:
        return False
    return pwd_context.verify(plain_password, user["hashad_password"])