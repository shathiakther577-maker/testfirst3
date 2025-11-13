from fastapi import APIRouter, Depends, Query, Body
from fastapi.security import OAuth2PasswordRequestForm

from api.v1.schemas import UserBalance, TransactionType, Transaction, \
    SetCallback, DropCallback
from api.v1.service import ApiService
from api.v1.security import ApiSecurity


api_v1_router = APIRouter()


@api_v1_router.post("/auth", include_in_schema=False)
async def auth_in_website(
        form_data: OAuth2PasswordRequestForm = Depends()
) -> dict:

    return ApiSecurity.authorization_in_website(form_data)


@api_v1_router.get("/balance", response_model=UserBalance)
async def get_user_balance(
        user_id: int = Depends(ApiSecurity.authorization_in_api)
) -> UserBalance:

    return ApiService().get_user_banalce(user_id)


@api_v1_router.get("/transactions", response_model=list[Transaction | None])
async def get_user_transactions(
        user_id: int = Depends(ApiSecurity.authorization_in_api),
        type: TransactionType = Query(
            default=TransactionType.ALL,
            description="Тип перевода."
        ),
        offset: int = Query(
            default=0,
            ge=0,
            description="Смещение, необходимое для выборки определённого подмножества записей."
        ),
        limit: int = Query(
            default=20,
            ge=1,
            le=100,
            description="Количество записей, которое необходимо получить."
        )
) -> list[Transaction | None]:

    return ApiService().get_user_transactions(user_id, type, offset, limit)


@api_v1_router.get("/user_verification", response_model=bool, include_in_schema=False)
def something(search_id: int) -> bool:

    return ApiService().user_verification(search_id)


@api_v1_router.post("/send_coins", response_model=Transaction)
async def send_coins(
        sender_id: int = Depends(ApiSecurity.authorization_in_api),
        recipient_id: int = Body(description="Идентификатор получателя"),
        amount: int = Body(default=0, ge=1, description="Cумма перевода")
) -> Transaction:

    return ApiService().send_coins(sender_id, recipient_id, amount)


@api_v1_router.post("/callback", response_model=SetCallback)
def set_callback_address(
        user_id: int = Depends(ApiSecurity.authorization_in_api),
        url: str = Body(
            default="",
            regex=r"\Ahttps?://[a-zA-Zа-яА-ЯёЁ0-9/._:-]{4,100}\Z",
            max_length=100,
            embed=True
        )
) -> SetCallback:

    return ApiService().set_callback_address(user_id, url)


@api_v1_router.delete("/callback", response_model=DropCallback)
def drop_callback_address(
        user_id: int = Depends(ApiSecurity.authorization_in_api),
) -> DropCallback:

    return ApiService().drop_callback_address(user_id)
