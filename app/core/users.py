from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

HARDCODED_USERS = {
    "admin@valente":{
        "username": "Administrator",
        "hashad_password": pwd_context.hash("AdminTech")
    },
    "lcpetro@pvbt":{
        "username":"LcPetro",
        "hashad_password": pwd_context.hash("pvbtcalc2025")
    },
    "pedro@aum":{
        "username":"Pedro Aum",
        "hashad_password": pwd_context.hash('PedroPvbt')
    },
    "claudio@lucas":{
        "username":"Cláudio Lucas",
        "hashad_password": pwd_context.hash('ClaudioPvbt')
    },
    "daniel@nobre":{
        "username":"Daniel Nobre",
        "hashad_password": pwd_context.hash('DanielPvbt')
    },
    "total@pvbt":{
        "username":"TotalEnergies",
        "hashad_password":pwd_context.hash('pvbtcalc2025')
    },
    "petrobras@pvbt":{
        "username":"Petrobras",
        "hashad_password":pwd_context.hash('pvbtcalc2025')
    }

}

def verify_user_password(plain_password: str, email: str) -> bool:
    user = HARDCODED_USERS.get(email)
    if not user:
        return False
    return pwd_context.verify(plain_password, user["hashad_password"])