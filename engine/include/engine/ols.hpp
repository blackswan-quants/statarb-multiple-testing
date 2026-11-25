#pragma once

#include <stdexcept>

#include <Eigen/Dense>

namespace engine {

// Raised when the inputs of a numerical routine have incompatible shapes.
class DimensionError : public std::invalid_argument {
public:
    using std::invalid_argument::invalid_argument;
};

// Output of an OLS regression.
struct OlsResult {
    Eigen::VectorXd beta;       // estimated coefficients, size p
    Eigen::VectorXd residuals;  // y - X * beta, size n
    double sigma2;              // residual variance, RSS / (n - p)
};

// Ordinary least squares regression of y on X.
//
// Parameters
//   X : n x p design matrix. Include a column of ones for the intercept.
//   y : response vector of size n.
//
// Returns
//   OlsResult with coefficients, residuals and residual variance.
//
// Throws
//   DimensionError if y.size() != X.rows() or if n <= p.
//
// Notes
//   Solved with column-pivoting Householder QR instead of the normal
//   equations (X'X)^-1 X'y: forming X'X squares the condition number,
//   which loses precision when factor returns are nearly collinear.
OlsResult ols(const Eigen::MatrixXd& X, const Eigen::VectorXd& y);

}  // namespace engine