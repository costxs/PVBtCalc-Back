from fastapi import APIRouter, HTTPException, Form
from app.core.security import create_access_token
from datetime import timedelta
from app.core.users import HARDCODED_USERS, verify_user_password
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/")
async def login_user(username:str = Form(...), password:str = Form(...)):
    user = HARDCODED_USERS.get(username)

    if not user or not verify_user_password(password, username):
        raise HTTPException(status_code=400, detail="Credenciais inválidas!")
    
    access_token_expires = timedelta(hours=4)
    access_token = create_access_token({"sub":username}, access_token_expires)

    return {"access_token":access_token, "token_type":"bearer", "user":user['username']}


