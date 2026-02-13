use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreateMaintenanceRecord, MaintenanceRecord};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<MaintenanceRecord>>, AppError> {
    let rows = sqlx::query_as::<_, MaintenanceRecord>("SELECT * FROM maintenance_records ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<MaintenanceRecord>, AppError> {
    let row = sqlx::query_as::<_, MaintenanceRecord>("SELECT * FROM maintenance_records WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateMaintenanceRecord>) -> Result<Json<MaintenanceRecord>, AppError> {
    let row = sqlx::query_as::<_, MaintenanceRecord>(
        "INSERT INTO maintenance_records (vehicle_id, maintenance_type, description, cost, maintenance_date, mileage_at_service, completed) \
         VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *",
    )
    .bind(b.vehicle_id)
    .bind(&b.maintenance_type)
    .bind(&b.description)
    .bind(&b.cost)
    .bind(b.maintenance_date)
    .bind(b.mileage_at_service)
    .bind(b.completed.unwrap_or(true))
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateMaintenanceRecord>) -> Result<Json<MaintenanceRecord>, AppError> {
    let row = sqlx::query_as::<_, MaintenanceRecord>(
        "UPDATE maintenance_records SET vehicle_id=$1, maintenance_type=$2, description=$3, cost=$4, \
         maintenance_date=$5, mileage_at_service=$6, completed=$7 WHERE id=$8 RETURNING *",
    )
    .bind(b.vehicle_id)
    .bind(&b.maintenance_type)
    .bind(&b.description)
    .bind(&b.cost)
    .bind(b.maintenance_date)
    .bind(b.mileage_at_service)
    .bind(b.completed.unwrap_or(true))
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM maintenance_records WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
