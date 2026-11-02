-- Fixed bill-type tags. They are system rows (household_id is null) and are
-- seeded both by this migration and by seed.sql (which calls the same function)
-- so production and local resets cannot drift.

set search_path = public, extensions;

create or replace function private.seed_system_tags()
returns void
language sql
security definer
set search_path = ''
as $$
  insert into public.tags (household_id, slug, label_en, label_hi, label_mr, kind, keywords)
  select null, v.slug, v.label_en, v.label_hi, v.label_mr, 'bill_type', v.keywords
  from (values
    ('electricity', 'Electricity', 'बिजली', 'वीज',
      array['electricity', 'MSEDCL', 'Adani Electricity', 'बिजली', 'वीज']),
    ('water', 'Water', 'पानी', 'पाणी',
      array['water', 'पानी', 'पाणी']),
    ('gas', 'Gas', 'गैस', 'गॅस',
      array['LPG', 'PNG', 'gas cylinder', 'गैस', 'गॅस']),
    ('internet-phone', 'Internet and Phone', 'इंटरनेट और फ़ोन', 'इंटरनेट आणि फोन',
      array['broadband', 'recharge', 'postpaid', 'wifi']),
    ('maintenance', 'Maintenance', 'मेंटेनेंस', 'देखभाल',
      array['society maintenance', 'मेंटेनेंस', 'देखभाल']),
    ('property-tax', 'Property Tax', 'संपत्ति कर', 'मालमत्ता कर',
      array['property tax', 'मालमत्ता कर']),
    ('electronics', 'Electronics and Appliances', 'इलेक्ट्रॉनिक्स और उपकरण', 'इलेक्ट्रॉनिक्स आणि उपकरणे',
      array['router', 'laptop', 'mixer', 'warranty card']),
    ('medical', 'Medical', 'चिकित्सा', 'वैद्यकीय',
      array['pharmacy', 'clinic', 'दवाई', 'औषध']),
    ('groceries', 'Groceries', 'किराना', 'किराणा',
      array['grocery', 'kirana', 'किराना', 'किराणा']),
    ('dining', 'Dining', 'भोजन', 'जेवण',
      array['restaurant', 'cafe', 'dining', 'hotel']),
    ('fuel', 'Fuel', 'ईंधन', 'इंधन',
      array['petrol', 'diesel', 'fuel', 'पेट्रोल', 'डीजल']),
    ('insurance', 'Insurance', 'बीमा', 'विमा',
      array['policy', 'premium', 'बीमा', 'विमा']),
    ('education', 'Education', 'शिक्षा', 'शिक्षण',
      array['school', 'tuition', 'fees', 'फीस']),
    ('repairs', 'Repairs', 'मरम्मत', 'दुरुस्ती',
      array['repair', 'service', 'मरम्मत', 'दुरुस्ती']),
    ('rent', 'Rent', 'किराया', 'भाडे',
      array['rent', 'lease', 'किराया', 'भाडे'])
  ) as v(slug, label_en, label_hi, label_mr, keywords)
  where not exists (
    select 1 from public.tags t
    where t.household_id is null and t.slug = v.slug
  );
$$;

revoke all on function private.seed_system_tags() from public;

select private.seed_system_tags();

insert into public.heartbeat (id, last_ping)
values (1, now())
on conflict (id) do update set last_ping = now();
