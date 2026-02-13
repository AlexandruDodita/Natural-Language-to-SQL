use axum::extract::State;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgRow;
use sqlx::{Column, PgPool, Row, TypeInfo};
use std::time::Instant;

#[derive(Deserialize)]
pub struct SqlRequest {
    query: String,
}

#[derive(Serialize)]
pub struct SqlResponse {
    columns: Vec<String>,
    rows: Vec<Vec<serde_json::Value>>,
    row_count: usize,
    duration_ms: f64,
}

#[derive(Serialize)]
struct SqlError {
    error: String,
}

pub async fn execute(
    State(pool): State<PgPool>,
    Json(req): Json<SqlRequest>,
) -> impl IntoResponse {
    let query = req.query.trim();
    if query.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "Empty query"})),
        );
    }

    let start = Instant::now();
    let result = sqlx::query(query).fetch_all(&pool).await;
    let duration_ms = start.elapsed().as_secs_f64() * 1000.0;

    match result {
        Ok(rows) => {
            let columns: Vec<String> = if rows.is_empty() {
                vec![]
            } else {
                rows[0].columns().iter().map(|c| c.name().to_string()).collect()
            };

            let json_rows: Vec<Vec<serde_json::Value>> = rows
                .iter()
                .map(|row| {
                    columns
                        .iter()
                        .enumerate()
                        .map(|(i, _)| pg_value_to_json(row, i))
                        .collect()
                })
                .collect();

            let row_count = json_rows.len();

            (
                StatusCode::OK,
                Json(serde_json::json!(SqlResponse {
                    columns,
                    rows: json_rows,
                    row_count,
                    duration_ms,
                })),
            )
        }
        Err(e) => (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!(SqlError {
                error: e.to_string()
            })),
        ),
    }
}

fn pg_value_to_json(row: &PgRow, idx: usize) -> serde_json::Value {
    let col = &row.columns()[idx];
    let type_name = col.type_info().name();

    macro_rules! try_get {
        ($t:ty) => {
            if let Ok(v) = row.try_get::<Option<$t>, _>(idx) {
                return match v {
                    Some(val) => serde_json::json!(val),
                    None => serde_json::Value::Null,
                };
            }
        };
    }

    match type_name {
        "BOOL" => try_get!(bool),
        "INT2" => try_get!(i16),
        "INT4" => try_get!(i32),
        "INT8" => try_get!(i64),
        "FLOAT4" => try_get!(f32),
        "FLOAT8" => try_get!(f64),
        "NUMERIC" | "MONEY" => {
            if let Ok(v) = row.try_get::<Option<rust_decimal::Decimal>, _>(idx) {
                return match v {
                    Some(val) => serde_json::json!(val.to_string()),
                    None => serde_json::Value::Null,
                };
            }
        }
        "DATE" => {
            if let Ok(v) = row.try_get::<Option<chrono::NaiveDate>, _>(idx) {
                return match v {
                    Some(val) => serde_json::json!(val.to_string()),
                    None => serde_json::Value::Null,
                };
            }
        }
        "TIMESTAMP" => {
            if let Ok(v) = row.try_get::<Option<chrono::NaiveDateTime>, _>(idx) {
                return match v {
                    Some(val) => serde_json::json!(val.to_string()),
                    None => serde_json::Value::Null,
                };
            }
        }
        "TIMESTAMPTZ" => {
            if let Ok(v) = row.try_get::<Option<chrono::DateTime<chrono::Utc>>, _>(idx) {
                return match v {
                    Some(val) => serde_json::json!(val.to_string()),
                    None => serde_json::Value::Null,
                };
            }
        }
        _ => {}
    }

    // fallback: try as string
    if let Ok(v) = row.try_get::<Option<String>, _>(idx) {
        return match v {
            Some(val) => serde_json::json!(val),
            None => serde_json::Value::Null,
        };
    }

    serde_json::Value::Null
}
