use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreateLocation, Location};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<Location>>, AppError> {
    let rows = sqlx::query_as::<_, Location>("SELECT * FROM locations ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<Location>, AppError> {
    let row = sqlx::query_as::<_, Location>("SELECT * FROM locations WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateLocation>) -> Result<Json<Location>, AppError> {
    let row = sqlx::query_as::<_, Location>(
        "INSERT INTO locations (name, city, address, phone) VALUES ($1,$2,$3,$4) RETURNING *",
    )
    .bind(&b.name)
    .bind(&b.city)
    .bind(&b.address)
    .bind(&b.phone)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateLocation>) -> Result<Json<Location>, AppError> {
    let row = sqlx::query_as::<_, Location>(
        "UPDATE locations SET name=$1, city=$2, address=$3, phone=$4 WHERE id=$5 RETURNING *",
    )
    .bind(&b.name)
    .bind(&b.city)
    .bind(&b.address)
    .bind(&b.phone)
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM locations WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
