use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{Client, CreateClient};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<Client>>, AppError> {
    let rows = sqlx::query_as::<_, Client>("SELECT * FROM clients ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<Client>, AppError> {
    let row = sqlx::query_as::<_, Client>("SELECT * FROM clients WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateClient>) -> Result<Json<Client>, AppError> {
    let row = sqlx::query_as::<_, Client>(
        "INSERT INTO clients (first_name, last_name, email, phone, drivers_license, date_of_birth, registration_date) \
         VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *",
    )
    .bind(&b.first_name)
    .bind(&b.last_name)
    .bind(&b.email)
    .bind(&b.phone)
    .bind(&b.drivers_license)
    .bind(b.date_of_birth)
    .bind(b.registration_date.unwrap_or(chrono::Local::now().date_naive()))
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateClient>) -> Result<Json<Client>, AppError> {
    let row = sqlx::query_as::<_, Client>(
        "UPDATE clients SET first_name=$1, last_name=$2, email=$3, phone=$4, drivers_license=$5, \
         date_of_birth=$6, registration_date=$7 WHERE id=$8 RETURNING *",
    )
    .bind(&b.first_name)
    .bind(&b.last_name)
    .bind(&b.email)
    .bind(&b.phone)
    .bind(&b.drivers_license)
    .bind(b.date_of_birth)
    .bind(b.registration_date.unwrap_or(chrono::Local::now().date_naive()))
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM clients WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
