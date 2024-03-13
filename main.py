from fastapi import FastAPI, Form, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from google.cloud import firestore
from google.auth.transport import requests
from google.oauth2 import id_token
from typing import Optional
from fastapi import Query
app = FastAPI()
db = firestore.Client()
from fastapi import Path
from fastapi import Path
import os


# Set the default Google Cloud project
os.environ.setdefault("GCLOUD_PROJECT", "fifth-citadel-416309")


app = FastAPI()
firestore_db = firestore.Client(project="fifth-citadel-416309")


templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

firebase_request_adapter = requests.Request()

async def verify_firebase_token(token: str):
    try:
        decoded_token = id_token.verify_firebase_token(token, firebase_request_adapter)
        return decoded_token
    except ValueError as e:
        print(f"Token verification failed: {e}")
        return None
    

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, attribute: Optional[str] = None, value: Optional[str] = None, max_value: Optional[str] = None):
    id_token_str = request.cookies.get("token")
    user_info = None
    if id_token_str:
        user_info = await verify_firebase_token(id_token_str)
    
    query = db.collection('cars')
    if attribute and value:
        if attribute in ['year', 'battery_size_kwh', 'wltp_range_km', 'cost', 'power_kw']:
            if max_value:
                query = query.where(attribute, '>=', float(value)).where(attribute, '<=', float(max_value))
            else:
                query = query.where(attribute, '==', float(value))
        else:
            query = query.where(attribute, '==', value)
    evs = query.stream()
    evs_data = [ev.to_dict() for ev in evs]
    
    return templates.TemplateResponse("main.html", {"request": request, "user_info": user_info, "evs": evs_data})

@app.post("/create-ev")
async def create_ev(request: Request, name: str = Form(...), manufacturer: str = Form(...), year: int = Form(...), battery_size_kwh: float = Form(...), wltp_range_km: int = Form(...), cost: float = Form(...), power_kw: int = Form(...)):
    ev_data = {
        'name': name,
        'manufacturer': manufacturer,
        'year': year,
        'battery_size_kwh': battery_size_kwh,
        'wltp_range_km': wltp_range_km,
        'cost': cost,
        'power_kw': power_kw
    }
    db.collection('cars').add(ev_data)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/add-ev", response_class=HTMLResponse)
async def add_ev_page(request: Request):
    id_token_str = request.cookies.get("token")
    user_info = None
    if id_token_str:
        user_info = await verify_firebase_token(id_token_str)
    if not user_info:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("add_ev.html", {"request": request})

@app.get("/ev/{name}", response_class=HTMLResponse)
async def get_ev(request: Request, name: str):
    id_token_str = request.cookies.get("token")
    user_info = None
    if id_token_str:
        user_info = await verify_firebase_token(id_token_str)

    ev_query = db.collection('cars').where('name', '==', name).limit(1)
    ev = ev_query.stream()
    ev_data = None
    for doc in ev:
        ev_data = doc.to_dict()
        break

    if not ev_data:
        raise HTTPException(status_code=404, detail="EV not found")

    # Fetch reviews for this EV from the database
    reviews_query = db.collection('reviews').where('ev_name', '==', name)
    reviews = reviews_query.stream()
    reviews_data = [review.to_dict() for review in reviews]

    return templates.TemplateResponse("ev_detail.html", {"request": request, "user_info": user_info, "ev": ev_data, "reviews": reviews_data})



@app.get("/edit-ev/{name}", response_class=HTMLResponse)
async def edit_ev_page(request: Request, name: str):
    id_token_str = request.cookies.get("token")
    user_info = None
    if id_token_str:
        user_info = await verify_firebase_token(id_token_str)

    ev_query = db.collection('cars').where('name', '==', name).limit(1)
    ev = ev_query.stream()
    ev_data = None
    for doc in ev:
        ev_data = doc.to_dict()
        break

    if not ev_data:
        raise HTTPException(status_code=404, detail="EV not found")

    return templates.TemplateResponse("edit_ev.html", {"request": request, "user_info": user_info, "ev": ev_data})

@app.post("/update-ev/{name}")
async def update_ev(request: Request, name: str, year: int = Form(...), battery_size_kwh: float = Form(...), wltp_range_km: int = Form(...), cost: float = Form(...), power_kw: int = Form(...)):
    ev_ref = db.collection('cars').where('name', '==', name).limit(1)
    ev = ev_ref.stream()
    ev_id = None
    for doc in ev:
        ev_id = doc.id
        break

    if not ev_id:
        raise HTTPException(status_code=404, detail="EV not found")

    ev_data = {
        'year': year,
        'battery_size_kwh': battery_size_kwh,
        'wltp_range_km': wltp_range_km,
        'cost': cost,
        'power_kw': power_kw
    }

    db.collection('evs').document(ev_id).update(ev_data)
    return RedirectResponse(url=f"/ev/{name}", status_code=status.HTTP_303_SEE_OTHER)


# Add a new route to handle the delete request
@app.post("/delete-ev/{name}")
async def delete_ev(request: Request, name: str):
    # Check if the user is logged in
    id_token_str = request.cookies.get("token")
    user_info = None
    if id_token_str:
        user_info = await verify_firebase_token(id_token_str)
    
    # If user is not logged in, redirect to the login page
    if not user_info:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    # Query the database to find the EV by name
    ev_query = db.collection('cars').where('name', '==', name).limit(1)
    ev = ev_query.stream()
    ev_id = None
    for doc in ev:
        ev_id = doc.id
        break

    # If EV not found, raise HTTPException with 404 status code
    if not ev_id:
        raise HTTPException(status_code=404, detail="EV not found")

    # Delete the EV from the database
    db.collection('evs').document(ev_id).delete()
    
    # Redirect to the home page after deletion
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/compare-evs", response_class=HTMLResponse)
async def compare_evs(request: Request, ev1: str = Query(...), ev2: str = Query(...)):
    ev1_data = None
    ev2_data = None
    
    # Retrieve EV data from Firestore
    ev_query = db.collection('cars').where('name', 'in', [ev1, ev2])
    evs = ev_query.stream()
    for ev in evs:
        ev_data = ev.to_dict()
        if ev_data['name'] == ev1:
            ev1_data = ev_data
        elif ev_data['name'] == ev2:
            ev2_data = ev_data
    
    # Check if both EVs are found
    if ev1_data is None or ev2_data is None:
        raise HTTPException(status_code=404, detail="One or more EVs not found")
    
    return templates.TemplateResponse("comparison_result.html", {"request": request, "ev1": ev1_data, "ev2": ev2_data})



@app.post("/submit-review")
async def submit_review(request: Request, ev_name: str = Form(...), review: str = Form(...), rating: int = Form(...)):
    # Check if the review and rating are valid
    if len(review.strip()) == 0 or rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Invalid review or rating")

    # Create a review document
    review_data = {
        'ev_name': ev_name,
        'review': review,
        'rating': rating
    }

    # Add the review to the database
    db.collection('reviews').add(review_data)

    # Redirect back to the EV detail page
    return RedirectResponse(url=f"/ev/{ev_name}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/submit-review")
async def submit_review(request: Request, ev_name: str = Form(...), review: str = Form(...), rating: int = Form(...)):
    # Check if the review and rating are valid
    if len(review.strip()) == 0 or rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Invalid review or rating")

    # Create a review document
    review_data = {
        'ev_name': ev_name,
        'review': review,
        'rating': rating
    }

    # Add the review to the database
    db.collection('reviews').add(review_data)

    # Redirect back to the EV detail page
    return RedirectResponse(url=f"/ev/{ev_name}", status_code=status.HTTP_303_SEE_OTHER)
