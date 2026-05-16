# LearnDash Integration

### LearnDash Architecture

LearnDash uses custom post types (`sfwd-courses`, `sfwd-lessons`, `sfwd-topic`, `sfwd-quiz`, `sfwd-question`) **with hierarchy managed via post meta rather than `post_parent`**. Course structure is stored in serialized meta (`ld_course_steps`). User progress is stored in `learndash_user_activity` and user meta. **Query progress via LearnDash API functions** (`learndash_user_get_course_progress`, `learndash_is_course_complete`) **rather than direct database queries** — internal schema changes between versions.

### LearnDash + WooCommerce Integration

Course enrollment tied to purchases flows through the official integration plugin. On `woocommerce_order_status_completed`, the integration enrolls users in associated courses. On refund, it revokes access. **Custom enrollment logic must respect this lifecycle.** **Avoid calling `ld_update_course_access()` without accounting for order state** — it creates enrollment records disconnected from purchase history, breaking refund handling and audit trails.

### LearnDash REST API

LearnDash exposes REST endpoints under `ldlms/v2` for courses, lessons, topics, quizzes, and user progress. Custom integrations authenticate via application passwords or JWT. **The API respects course access settings.** Extend via `rest_api_init` for custom reporting or progress tracking endpoints that aggregate LearnDash data with business-specific metrics.

---
[Back to Overview](./OVERVIEW.md)
