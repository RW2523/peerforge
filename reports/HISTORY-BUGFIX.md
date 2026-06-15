# History Feature - Bug Fix

## Issue

When trying to access the History page (`/history`), users encountered a "Failed to fetch" error in the browser console:

```
TypeError: Failed to fetch
    at Module.listDebates (src/lib/api.ts:482:26)
    at async loadDebates (src/app/history/page.tsx:39:23)
```

## Root Cause

The backend API was returning a 500 Internal Server Error with:

```
AttributeError: 'str' object has no attribute 'get'
INFO: 127.0.0.1:59290 - "GET /debates?workspace_id=00000000-0000-0000-0000-000000000101&limit=50 HTTP/1.1" 500 Internal Server Error
```

### The Problem

In `/apps/api/src/routes/debates.py` line 37, the `check_workspace_access()` function was being called with arguments in the wrong order:

```python
# INCORRECT (arguments swapped)
check_workspace_access(workspace_id, current_user)
```

The function signature expects:
```python
def check_workspace_access(
    user: Dict[str, Any],
    resource_workspace_id: str
) -> None:
```

So it should be called as:
```python
# CORRECT
check_workspace_access(current_user, workspace_id)
```

When the arguments were swapped:
- `workspace_id` (a string) was passed as the `user` parameter
- The function tried to call `.get()` on the string, causing the AttributeError
- The backend crashed with a 500 error
- The frontend saw this as a "Failed to fetch" error

## Solution

### Backend Fix

**File**: `/apps/api/src/routes/debates.py` (line 37)

```python
# Before
if current_user:
    check_workspace_access(workspace_id, current_user)

# After
if current_user:
    check_workspace_access(current_user, workspace_id)
```

### Frontend Enhancement

**File**: `/apps/web/src/app/history/page.tsx`

Enhanced error handling to provide helpful messages:

```typescript
// Improved error handling
catch (err) {
  const errorMessage = err instanceof Error ? err.message : 'Failed to load debates';
  
  // Provide helpful error message if backend is not running
  if (errorMessage.includes('Failed to fetch') || errorMessage.includes('fetch')) {
    setError('Unable to connect to backend server. Please ensure the API server is running on http://localhost:8000');
  } else {
    setError(errorMessage);
  }
}
```

Added inline help text for backend startup:
```jsx
{error.includes('backend server') && (
  <div style={{ marginTop: '8px', fontSize: '12px' }}>
    Start the backend: <code>cd apps/api && python -m uvicorn src.main:app --reload</code>
  </div>
)}
```

## Testing

After the fix:
1. ✅ Backend no longer crashes on `GET /debates` request
2. ✅ Frontend successfully loads debate list
3. ✅ History page displays correctly
4. ✅ Error handling provides helpful messages if backend is down

## Impact

- **Severity**: Critical (feature completely non-functional)
- **Scope**: Affects all users trying to access History page
- **Fix Type**: Single line change in backend
- **Risk**: Low (correct function signature, no side effects)

## Prevention

This type of error could be prevented by:
1. Using type hints consistently (already in place)
2. Adding unit tests for route handlers
3. Integration tests for API endpoints
4. Linting tools that catch argument order issues

## Related Files

- `/apps/api/src/routes/debates.py` - Fixed
- `/apps/web/src/app/history/page.tsx` - Enhanced error handling
- `/apps/api/src/auth.py` - Function definition reference

## Status

✅ **Fixed and Tested**

The History feature is now fully functional.
