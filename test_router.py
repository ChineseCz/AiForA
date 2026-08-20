from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

router = APIRouter(prefix='/api/user')

@router.get('/test')
def test():
    return {'ok': True}

app = FastAPI()
app.include_router(router)

client = TestClient(app)
response = client.get('/api/user/test')
print('Status:', response.status_code)
print('Body:', response.json())
