#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>

#include <cmath>

#include "engine/ols.hpp"

using Catch::Matchers::WithinAbs;

TEST_CASE("OLS recovers known coefficients from noiseless data", "[ols]") {
    // True model: y = 1 + 2 x1 - 3 x2, with no error term
    const int n = 50;
    Eigen::MatrixXd X(n, 3);
    Eigen::VectorXd y(n);
    for (int i = 0; i < n; ++i) {
        const double x1 = 0.1 * i;
        const double x2 = std::sin(0.3 * i);
        X(i, 0) = 1.0;  // intercept column
        X(i, 1) = x1;
        X(i, 2) = x2;
        y(i) = 1.0 + 2.0 * x1 - 3.0 * x2;
    }

    const auto res = engine::ols(X, y);

    REQUIRE_THAT(res.beta(0), WithinAbs(1.0, 1e-10));
    REQUIRE_THAT(res.beta(1), WithinAbs(2.0, 1e-10));
    REQUIRE_THAT(res.beta(2), WithinAbs(-3.0, 1e-10));
    REQUIRE(res.residuals.norm() < 1e-9);
}