from fastapi import APIRouter, HTTPException, Query
from ..database import db 
from ..schemas import CenterResult
from typing import List, Optional
from datetime import datetime, time
router = APIRouter()
@router.get("/api/v1/search/", response_model=List[CenterResult])
async def search_courts(
    date :str,
    start_time :str,
    end_time :str,
    address: Optional[str] = Query(None)
):
    pool = db.pg_pool
    if not pool:
        raise HTTPException(status_code=500, detail="DB not connected")
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        
        start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        end_time_obj = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Sai định dạng ngày giờ (YYYY-MM-DD và HH:MM)")
    address_filter ="%"
    if not address or address.strip() == "" or address == "Tất cả khu vực":
        address_filter = "%"
    else:
        address_filter = f"%{address}%"
    sql = """
    SELECT 
        center.id as center_id,
        center.name as center_name,
        center.address,
        center.open_time,
        center.close_time,
        center.image as center_image,
        court.id as court_id,
        court.name as court_name,
        court.type_court,
        CASE 
            WHEN court.golden_start_time IS NOT NULL 
                 AND $2::time >= court.golden_start_time 
                 AND $3::time <= court.golden_end_time 
            THEN court.golden_price_per_hour
            ELSE court.base_price_per_hour 
        END as calculated_price
    FROM partner_badmintoncenter center
    JOIN partner_court court ON center.id = court.center_id
    WHERE 
        center.is_active = true
        AND court.is_active = true
        AND center.address ILIKE $4
        AND center.open_time <= $2::time
        AND center.close_time >= $3::time
        AND NOT EXISTS (
            SELECT 1 FROM booking_booking b
            WHERE b.court_id = court.id
            AND b.date = $1::date
            AND b.status IN ('confirmed', 'pending', 'waiting_verify')
            AND (b.start_time < $3::time AND b.end_time > $2::time)
        )
    ORDER BY center.id, calculated_price ASC
    """

    rows = await pool.fetch(sql, date_obj, start_time_obj, end_time_obj, address_filter)
    redis = db.redis_client
    locked_courts = set()
    if redis and rows:
        check_keys = []
        court_ids_map = []
        unique_court_ids = set(row['court_id'] for row in rows)
        for c_id in unique_court_ids:
            key = f"lock:court_{c_id}_{date}_{start_time}"
            check_keys.append(key)
            court_ids_map.append(c_id)
        if check_keys:
            values = await redis.mget(check_keys)
            for i, val in enumerate(values):
                if val is not None:
                    locked_courts.add(court_ids_map[i])
    centers_map = {}
    for row in rows:
        c_id = row['center_id']
        court_id = row['court_id']
        if court_id in locked_courts:
            continue
        if c_id not in centers_map:
            centers_map[c_id] = {
                "id": row['center_id'],
                "name": row['center_name'],
                "address": row['address'],
                "image": f"/media/{row['center_image']}" if row['center_image'] else None,
                "open_time": str(row['open_time'])[:5],
                "close_time": str(row['close_time'])[:5],
                "lowest_price": float('inf'),
                "available_courts": []
            }
        price = int(row['calculated_price'])if row['calculated_price'] else 0
        courts_obj = {
            "id": row['court_id'],
            "name": row['court_name'],
            "type_court": row['type_court'],
            "price": price
        }
        centers_map[c_id]["available_courts"].append(courts_obj)
        if price < centers_map[c_id]["lowest_price"]:
            centers_map[c_id]["lowest_price"] = price
    results = list(centers_map.values())
    for r in results:
        if r["lowest_price"] == float('inf'):
            r["lowest_price"] = 0
    return results




@router.get("/api/v1/districts/")
async def get_hanoi_districts():
    return [
        "Ba Đình", "Hoàn Kiếm", "Tây Hồ", "Long Biên", "Cầu Giấy", 
        "Đống Đa", "Hai Bà Trưng", "Hoàng Mai", "Thanh Xuân", 
        "Nam Từ Liêm", "Bắc Từ Liêm", "Hà Đông", "Sơn Tây", 
        "Ba Vì", "Phúc Thọ", "Đan Phượng", "Hoài Đức", "Thạch Thất", 
        "Quốc Oai", "Thanh Trì", "Thường Tín", "Phú Xuyên", 
        "Mê Linh", "Đông Anh", "Sóc Sơn", "Gia Lâm"
    ]