use axum::extract::{Path, State};
use axum::Json;
use sqlx::PgPool;

use crate::error::AppError;
use crate::models::{CreateEmployee, Employee};

pub async fn list(State(pool): State<PgPool>) -> Result<Json<Vec<Employee>>, AppError> {
    let rows = sqlx::query_as::<_, Employee>("SELECT * FROM employees ORDER BY id")
        .fetch_all(&pool)
        .await?;
    Ok(Json(rows))
}

pub async fn get_one(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<Employee>, AppError> {
    let row = sqlx::query_as::<_, Employee>("SELECT * FROM employees WHERE id = $1")
        .bind(id)
        .fetch_one(&pool)
        .await?;
    Ok(Json(row))
}

pub async fn create(State(pool): State<PgPool>, Json(b): Json<CreateEmployee>) -> Result<Json<Employee>, AppError> {
    let row = sqlx::query_as::<_, Employee>(
        "INSERT INTO employees (location_id, first_name, last_name, role, salary, hire_date, email, phone) \
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
    )
    .bind(b.location_id)
    .bind(&b.first_name)
    .bind(&b.last_name)
    .bind(&b.role)
    .bind(&b.salary)
    .bind(b.hire_date)
    .bind(&b.email)
    .bind(&b.phone)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn update(State(pool): State<PgPool>, Path(id): Path<i32>, Json(b): Json<CreateEmployee>) -> Result<Json<Employee>, AppError> {
    let row = sqlx::query_as::<_, Employee>(
        "UPDATE employees SET location_id=$1, first_name=$2, last_name=$3, role=$4, salary=$5, \
         hire_date=$6, email=$7, phone=$8 WHERE id=$9 RETURNING *",
    )
    .bind(b.location_id)
    .bind(&b.first_name)
    .bind(&b.last_name)
    .bind(&b.role)
    .bind(&b.salary)
    .bind(b.hire_date)
    .bind(&b.email)
    .bind(&b.phone)
    .bind(id)
    .fetch_one(&pool)
    .await?;
    Ok(Json(row))
}

pub async fn delete(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<serde_json::Value>, AppError> {
    sqlx::query("DELETE FROM employees WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await?;
    Ok(Json(serde_json::json!({"deleted": id})))
}
