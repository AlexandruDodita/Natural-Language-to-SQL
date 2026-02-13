use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreatePayment, Payment};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<Payment>>, AppError> {
    let rows = sqlx::query_as::<_, Payment>("SELECT * FROM payments ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<Payment>, AppError> {
    let row = sqlx::query_as::<_, Payment>("SELECT * FROM payments WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreatePayment>) -> Result<Json<Payment>, AppError> {
    let row = sqlx::query_as::<_, Payment>(
        "INSERT INTO payments (reservation_id, amount, payment_method, payment_date, status) \
         VALUES ($1,$2,$3,$4,$5) RETURNING *",
    )
    .bind(b.reservation_id)
    .bind(&b.amount)
    .bind(&b.payment_method)
    .bind(b.payment_date)
    .bind(b.status.as_deref().unwrap_or("completed"))
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreatePayment>) -> Result<Json<Payment>, AppError> {
    let row = sqlx::query_as::<_, Payment>(
        "UPDATE payments SET reservation_id=$1, amount=$2, payment_method=$3, payment_date=$4, status=$5 \
         WHERE id=$6 RETURNING *",
    )
    .bind(b.reservation_id)
    .bind(&b.amount)
    .bind(&b.payment_method)
    .bind(b.payment_date)
    .bind(b.status.as_deref().unwrap_or("completed"))
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM payments WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
