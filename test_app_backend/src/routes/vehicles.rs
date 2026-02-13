use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreateVehicle, Vehicle};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<Vehicle>>, AppError> {
    let rows = sqlx::query_as::<_, Vehicle>("SELECT * FROM vehicles ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<Vehicle>, AppError> {
    let row = sqlx::query_as::<_, Vehicle>("SELECT * FROM vehicles WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateVehicle>) -> Result<Json<Vehicle>, AppError> {
    let row = sqlx::query_as::<_, Vehicle>(
        "INSERT INTO vehicles (category_id, location_id, make, model, year, license_plate, color, daily_rate, mileage, status) \
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING *",
    )
    .bind(b.category_id)
    .bind(b.location_id)
    .bind(&b.make)
    .bind(&b.model)
    .bind(b.year)
    .bind(&b.license_plate)
    .bind(&b.color)
    .bind(&b.daily_rate)
    .bind(b.mileage.unwrap_or(0))
    .bind(b.status.as_deref().unwrap_or("available"))
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateVehicle>) -> Result<Json<Vehicle>, AppError> {
    let row = sqlx::query_as::<_, Vehicle>(
        "UPDATE vehicles SET category_id=$1, location_id=$2, make=$3, model=$4, year=$5, \
         license_plate=$6, color=$7, daily_rate=$8, mileage=$9, status=$10 WHERE id=$11 RETURNING *",
    )
    .bind(b.category_id)
    .bind(b.location_id)
    .bind(&b.make)
    .bind(&b.model)
    .bind(b.year)
    .bind(&b.license_plate)
    .bind(&b.color)
    .bind(&b.daily_rate)
    .bind(b.mileage.unwrap_or(0))
    .bind(b.status.as_deref().unwrap_or("available"))
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM vehicles WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
