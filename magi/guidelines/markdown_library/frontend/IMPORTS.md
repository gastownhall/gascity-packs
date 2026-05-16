# Code Organization and Imports

### Import Order

```typescript
// 1. React imports
import { useState, useEffect, useMemo, useCallback, memo } from 'react'
import type { FC, ReactNode } from 'react'

// 2. Third-party libraries
import { useQuery, useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import clsx from 'clsx'

// 3. Store imports
import { useAuthStore } from '@store/authStore'
import { useUIStore } from '@store/uiStore'

// 4. Service/API imports
import { userApi } from '@services/api/users'
import { authService } from '@services/auth'

// 5. Component imports
import Layout from '@components/layout/Layout'
import Button from '@components/shared/Button'
import UserCard from '@components/users/UserCard'

// 6. Hook imports
import { useDebounce } from '@hooks/useDebounce'
import { useMediaQuery } from '@hooks/useMediaQuery'

// 7. Type imports
import type { User, UserRole } from '@types/user'
import type { ApiResponse } from '@types/api'

// 8. Utility imports
import { formatDate, formatCurrency } from '@utils/format'
import { validateEmail } from '@utils/validation'

// 9. Style imports
import styles from './Component.module.css'
```

**Import Rules:**

1. React imports first.
2. Third-party library imports.
3. Store imports.
4. Service/API imports.
5. Component imports.
6. Hook imports.
7. Type imports (use `type` keyword).
8. Utility imports.
9. Style imports.

Separate groups with blank lines. Use path aliases, never relative imports beyond parent directory. Sort alphabetically within each group.

---
[Back to Overview](./OVERVIEW.md)
