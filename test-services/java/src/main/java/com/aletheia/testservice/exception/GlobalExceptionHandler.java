package com.aletheia.testservice.exception;

import com.aletheia.testservice.model.ErrorResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.sql.SQLException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(NullPointerException.class)
    public ResponseEntity<ErrorResponse> handleNullPointerException(NullPointerException ex) {
        String requestId = MDC.get("request_id");
        logger.error("NullPointerException occurred (request_id={})", requestId, ex);
        
        ErrorResponse response = new ErrorResponse(
                ex.getMessage() != null ? ex.getMessage() : "Null pointer exception",
                "null_pointer_exception",
                ex.getClass().getName(),
                requestId,
                ex.getStackTrace()
        );
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    @ExceptionHandler(ArrayIndexOutOfBoundsException.class)
    public ResponseEntity<ErrorResponse> handleArrayIndexOutOfBoundsException(ArrayIndexOutOfBoundsException ex) {
        String requestId = MDC.get("request_id");
        logger.error("ArrayIndexOutOfBoundsException occurred (request_id={})", requestId, ex);
        
        ErrorResponse response = new ErrorResponse(
                ex.getMessage(),
                "array_index_out_of_bounds",
                ex.getClass().getName(),
                requestId,
                ex.getStackTrace()
        );
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    @ExceptionHandler(ArithmeticException.class)
    public ResponseEntity<ErrorResponse> handleArithmeticException(ArithmeticException ex) {
        String requestId = MDC.get("request_id");
        logger.error("ArithmeticException occurred (request_id={})", requestId, ex);
        
        ErrorResponse response = new ErrorResponse(
                ex.getMessage(),
                "arithmetic_exception",
                ex.getClass().getName(),
                requestId,
                ex.getStackTrace()
        );
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    @ExceptionHandler(SQLException.class)
    public ResponseEntity<ErrorResponse> handleSQLException(SQLException ex) {
        String requestId = MDC.get("request_id");
        logger.error("SQLException occurred (request_id={}, sqlState={}, errorCode={})", 
                requestId, ex.getSQLState(), ex.getErrorCode(), ex);
        
        ErrorResponse response = new ErrorResponse(
                ex.getMessage(),
                "sql_exception",
                ex.getClass().getName(),
                requestId,
                ex.getStackTrace()
        );
        
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
    }

    @ExceptionHandler(OutOfMemoryError.class)
    public ResponseEntity<ErrorResponse> handleOutOfMemoryError(OutOfMemoryError ex) {
        String requestId = MDC.get("request_id");
        logger.error("OutOfMemoryError occurred (request_id={})", requestId, ex);
        
        ErrorResponse response = new ErrorResponse(
                ex.getMessage(),
                "out_of_memory_error",
                ex.getClass().getName(),
                requestId,
                ex.getStackTrace()
        );
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    @ExceptionHandler(RuntimeException.class)
    public ResponseEntity<ErrorResponse> handleRuntimeException(RuntimeException ex) {
        String requestId = MDC.get("request_id");
        
        // Check if the cause is one of our handled exceptions
        Throwable cause = ex.getCause();
        if (cause instanceof NullPointerException) {
            return handleNullPointerException((NullPointerException) cause);
        } else if (cause instanceof ArrayIndexOutOfBoundsException) {
            return handleArrayIndexOutOfBoundsException((ArrayIndexOutOfBoundsException) cause);
        } else if (cause instanceof ArithmeticException) {
            return handleArithmeticException((ArithmeticException) cause);
        } else if (cause instanceof SQLException) {
            return handleSQLException((SQLException) cause);
        }
        
        logger.error("RuntimeException occurred (request_id={})", requestId, ex);
        
        ErrorResponse response = new ErrorResponse(
                ex.getMessage(),
                "runtime_exception",
                ex.getClass().getName(),
                requestId,
                ex.getStackTrace()
        );
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGenericException(Exception ex) {
        String requestId = MDC.get("request_id");
        logger.error("Unexpected exception occurred (request_id={})", requestId, ex);
        
        ErrorResponse response = new ErrorResponse(
                ex.getMessage(),
                "unexpected_exception",
                ex.getClass().getName(),
                requestId,
                ex.getStackTrace()
        );
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }
}
