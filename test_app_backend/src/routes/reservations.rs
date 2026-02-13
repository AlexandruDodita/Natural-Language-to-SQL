use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreateReservation, Reservation};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<Reservation>>, AppError> {
    let rows = sqlx::query_as::<_, Reservation>("SELECT * FROM reservations ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<Reservation>, AppError> {
    let row = sqlx::query_as::<_, Reservation>("SELECT * FROM reservations WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateReservation>) -> Result<Json<Reservation>, AppError> {
    let row = sqlx::query_as::<_, Reservation>(
        "INSERT INTO reservations (client_id, vehicle_id, pickup_location, return_location, pickup_date, return_date, status, total_cost) \
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
    )
    .bind(b.client_id)
    .bind(b.vehicle_id)
    .bind(b.pickup_location)
    .bind(b.return_location)
    .bind(b.pickup_date)
    .bind(b.return_date)
    .bind(b.status.as_deref().unwrap_or("confirmed"))
    .bind(&b.total_cost)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateReservation>) -> Result<Json<Reservation>, AppError> {
    let row = sqlx::query_as::<_, Reservation>(
        "UPDATE reservations SET client_id=$1, vehicle_id=$2, pickup_location=$3, return_location=$4, \
         pickup_date=$5, return_date=$6, status=$7, total_cost=$8 WHERE id=$9 RETURNING *",
    )
    .bind(b.client_id)
    .bind(b.vehicle_id)
    .bind(b.pickup_location)
    .bind(b.return_location)
    .bind(b.pickup_date)
    .bind(b.return_date)
    .bind(b.status.as_deref().unwrap_or("confirmed"))
    .bind(&b.total_cost)
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM reservations WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
