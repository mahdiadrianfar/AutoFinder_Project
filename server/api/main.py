from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from server.database.connection import SessionLocal
from server.models import Ad, init_db
from server.scraper.base import scrape_divar_list

app = FastAPI(title="AutoIndex API", version="0.1.0")


@app.on_event("startup")
def startup_event():
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ScrapeRequest(BaseModel):
    url: HttpUrl


class AdResponse(BaseModel):
    id: int
    url: str
    title: Optional[str] = None
    price: Optional[str] = None
    price_value: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    scraped_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ads/scrape", response_model=List[AdResponse])
def scrape_ads(request: ScrapeRequest, db: Session = Depends(get_db)):
    ads = scrape_divar_list(str(request.url))
    saved_ads: List[Ad] = []

    for ad_data in ads:
        if not ad_data.get("url"):
            continue

        existing_ad = db.query(Ad).filter(Ad.url == ad_data["url"]).first()
        if existing_ad:
            existing_ad.title = ad_data.get("title") or existing_ad.title
            existing_ad.price = ad_data.get("price") or existing_ad.price
            existing_ad.price_value = ad_data.get(
                "price_value") or existing_ad.price_value
            existing_ad.location = ad_data.get(
                "location") or existing_ad.location
            existing_ad.description = ad_data.get(
                "description") or existing_ad.description
            existing_ad.source = ad_data.get("source") or existing_ad.source
            existing_ad.scraped_at = datetime.utcnow()
            existing_ad.raw_data = ad_data.get(
                "raw_data") or existing_ad.raw_data
            saved_ads.append(existing_ad)
        else:
            new_ad = Ad(
                url=ad_data["url"],
                title=ad_data.get("title"),
                price=ad_data.get("price"),
                price_value=ad_data.get("price_value"),
                location=ad_data.get("location"),
                description=ad_data.get("description"),
                source=ad_data.get("source"),
                scraped_at=datetime.utcnow(),
                raw_data=ad_data.get("raw_data"),
            )
            db.add(new_ad)
            saved_ads.append(new_ad)

    db.commit()
    return saved_ads


@app.get("/ads", response_model=List[AdResponse])
def list_ads(
    title: Optional[str] = Query(None, description="Search term for ad title"),
    location: Optional[str] = Query(
        None, description="Search term for ad location"),
    min_price: Optional[int] = Query(None, description="Minimum price filter"),
    max_price: Optional[int] = Query(None, description="Maximum price filter"),
    sort_by: str = Query(
        "scraped_at", pattern="^(scraped_at|price_value|title)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Ad)

    if title:
        query = query.filter(Ad.title.ilike(f"%{title}%"))
    if location:
        query = query.filter(Ad.location.ilike(f"%{location}%"))
    if min_price is not None:
        query = query.filter(Ad.price_value >= min_price)
    if max_price is not None:
        query = query.filter(Ad.price_value <= max_price)

    order_field = getattr(Ad, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(order_field))
    else:
        query = query.order_by(asc(order_field))

    return query.offset(offset).limit(limit).all()


@app.get("/ads/{ad_id}", response_model=AdResponse)
def get_ad(ad_id: int, db: Session = Depends(get_db)):
    ad = db.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return ad
