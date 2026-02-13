use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use serde_json::json;

pub struct AppError(pub StatusCode, pub String);

impl IntoResponse for AppError {
    fn into_response(self) -> axum::response::Response {
        let body = Json(json!({ "error": self.1 }));
        (self.0, body).into_response()
    }
}

impl From<sqlx::Error> for AppError {
    fn from(err: sqlx::Error) -> Self {
        match err {
            sqlx::Error::RowNotFound => {
                AppError(StatusCode::NOT_FOUND, "Not found".into())
            }
            _ => AppError(StatusCode::INTERNAL_SERVER_ERROR, err.to_string()),
        }
    }
}
