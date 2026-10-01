import json
from app.database.supabase_client import get_supabase_client

supa = get_supabase_client()
print('Fetching latest draft...')
draft_res = supa.table('post_drafts').select('*').order('created_at', desc=True).limit(1).execute()
draft = draft_res.data[0] if draft_res.data else None
print(f'\n--- LATEST DRAFT ---\n{json.dumps(draft, indent=2)}' if draft else 'No drafts found.')

run_id = draft.get('run_id') if draft else None
if run_id:
    run = supa.table('post_runs').select('*').eq('id', run_id).single().execute().data
    print(f'\n--- RUN IDEAS ---\n{json.dumps(run.get("ideas", []), indent=2)}')
    print(f'\n--- RUN RESEARCH ---\n{json.dumps(run.get("research_data", {}), indent=2)}')
else:
    print('No run found.')
