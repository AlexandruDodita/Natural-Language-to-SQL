use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreateVehicleCategory, VehicleCategory};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<VehicleCategory>>, AppError> {
    let rows = sqlx::query_as::<_, VehicleCategory>("SELECT * FROM vehicle_categories ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<VehicleCategory>, AppError> {
    let row = sqlx::query_as::<_, VehicleCategory>("SELECT * FROM vehicle_categories WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateVehicleCategory>) -> Result<Json<VehicleCategory>, AppError> {
    let row = sqlx::query_as::<_, VehicleCategory>(
        "INSERT INTO vehicle_categories (name, description, daily_rate_min, daily_rate_max) \
         VALUES ($1,$2,$3,$4) RETURNING *",
    )
    .bind(&b.name)
    .bind(&b.description)
    .bind(&b.daily_rate_min)
    .bind(&b.daily_rate_max)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateVehicleCategory>) -> Result<Json<VehicleCategory>, AppError> {
    let row = sqlx::query_as::<_, VehicleCategory>(
        "UPDATE vehicle_categories SET name=$1, description=$2, daily_rate_min=$3, daily_rate_max=$4 \
         WHERE id=$5 RETURNING *",
    )
    .bind(&b.name)
    .bind(&b.description)
    .bind(&b.daily_rate_min)
    .bind(&b.daily_rate_max)
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM vehicle_categories WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
