from pydantic import BaseModel
from typing import Optional


class BotRequest(BaseModel):
    passengerId: str
    input_msg: str
    interrupt_status: Optional[str] = None
    interrupt_user_input: Optional[str] = None

