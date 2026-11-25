#include "engine/ols.hpp"

namespace engine {

OlsResult ols(const Eigen::MatrixXd& X, const Eigen::VectorXd& y) {
    const Eigen::Index n = X.rows();
    const Eigen::Index p = X.cols();

    if (y.size() != n) {
        throw DimensionError("ols: X and y must have the same number of rows");
    }
    if (n <= p) {
        throw DimensionError("ols: need more observations than regressors (n > p)");
    }

    OlsResult result;
    result.beta = X.colPivHouseholderQr().solve(y);
    result.residuals = y - X * result.beta;
    result.sigma2 = result.residuals.squaredNorm() / static_cast<double>(n - p);
    return result;
}

}  // namespace engine