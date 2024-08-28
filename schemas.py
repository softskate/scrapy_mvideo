from pydantic import BaseModel, ConfigDict
from typing import Optional


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    productUrl: str
    name: str
    price: int
    imageUrls: list
    brandName: Optional[str] = None
    details: Optional[dict] = None
    
class ParsingItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    link: str
