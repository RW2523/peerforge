# Arinar Web - Operator UI

Next.js-based operator interface for Arinar debates.

## Auth Setup

### Local Development

1. **Start Supabase local stack** (from repo root):
   ```bash
   cd /path/to/arinar-v2
   make db-up
   ```
   
   This starts Supabase on `http://localhost:54321`.

2. **Configure environment**:
   ```bash
   cp .env.example .env.local
   ```
   
   Update `.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<get-from-supabase-local-output>
   ```
   
   **Getting the anon key**: Run `make db-up` and look for the "API Keys" section in the output, or check `infra/docker/.env` for `ANON_KEY`.

3. **Create a test user** (via Supabase Studio):
   - Open http://localhost:54323 (Supabase Studio)
   - Go to "Authentication" > "Users"
   - Click "Add User"
   - Email: `test@example.com`, Password: `password123`
   - Note the user ID

4. **Map user to workspace**:
   ```sql
   -- Connect to DB: make db-shell
   INSERT INTO user_workspaces (user_id, workspace_id, role)
   VALUES 
     ('your-user-id', '00000000-0000-0000-0000-000000000101', 'owner');
   ```

5. **Start the web app**:
   ```bash
   npm install
   npm run dev
   ```
   
   Open http://localhost:3000/login

### Cloud / Production

1. **Supabase Project**:
   - Create a project at https://supabase.com
   - Enable Email auth in Authentication settings
   - Get Project URL and anon key from Settings > API

2. **Environment variables**:
   ```env
   NEXT_PUBLIC_API_URL=https://your-api-domain.com
   NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
   ```

3. **User-Workspace Mapping**:
   - Users must be mapped to workspaces in the `user_workspaces` table
   - Add mappings via SQL or admin API:
     ```sql
     INSERT INTO user_workspaces (user_id, workspace_id, role)
     VALUES 
       (auth.uid(), 'workspace-uuid', 'member');
     ```

4. **Deploy**:
   ```bash
   npm run build
   npm start
   ```

## Auth Flow

1. User visits `/login`
2. Enters email/password or requests magic link
3. On success, Supabase session is created
4. All API requests include `Authorization: Bearer <supabase_access_token>`
5. API validates JWT and resolves `workspace_id` from `user_workspaces` table
6. User can access debates in their workspace

## Workspace Resolution

The API resolves workspace access as follows:

1. **JWT contains `workspace_id` claim** (custom auth hook):
   - Use workspace_id directly from JWT
   
2. **JWT does NOT contain `workspace_id` claim** (default Supabase):
   - Extract `user_id` from JWT (`sub` claim)
   - Query `user_workspaces` table for user's workspace
   - Use the first workspace found

Users must be mapped to at least one workspace to access debates.

## Logout

Visit `/logout` or call `signOut()` from `@/lib/supabase`.

## Development Scripts

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```
