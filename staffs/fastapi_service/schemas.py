from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class CourtResult(BaseModel):
    id:int
    name : str
    type_court : str
    price : int

class CenterResult(BaseModel):
    id : UUID
    name : str
    address : str
    image : Optional[str] = None
    open_time : str
    close_time : str
    lowest_price : int
    available_courts: List[CourtResult]