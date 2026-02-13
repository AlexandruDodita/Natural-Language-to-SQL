use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreateReview, Review};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<Review>>, AppError> {
    let rows = sqlx::query_as::<_, Review>("SELECT * FROM reviews ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<Review>, AppError> {
    let row = sqlx::query_as::<_, Review>("SELECT * FROM reviews WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateReview>) -> Result<Json<Review>, AppError> {
    let row = sqlx::query_as::<_, Review>(
        "INSERT INTO reviews (reservation_id, rating, comment, review_date) \
         VALUES ($1,$2,$3,$4) RETURNING *",
    )
    .bind(b.reservation_id)
    .bind(b.rating)
    .bind(&b.comment)
    .bind(b.review_date)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateReview>) -> Result<Json<Review>, AppError> {
    let row = sqlx::query_as::<_, Review>(
        "UPDATE reviews SET reservation_id=$1, rating=$2, comment=$3, review_date=$4 \
         WHERE id=$5 RETURNING *",
    )
    .bind(b.reservation_id)
    .bind(b.rating)
    .bind(&b.comment)
    .bind(b.review_date)
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM reviews WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
