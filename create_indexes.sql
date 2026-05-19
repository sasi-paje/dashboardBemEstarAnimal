-- Índices MUITO USADOS - Executar no banco de produção

-- sk_booking: ux_booking_unique_slot_res
CREATE UNIQUE INDEX IF NOT EXISTS ux_booking_unique_slot_res ON public.sk_booking USING btree (client_id, id_campaign, id_site_sevice, service_date, init_interval_hour, end_interval_hour, resource_no);

-- sk_booking: idx_booking_preview_lookup
CREATE INDEX IF NOT EXISTS idx_booking_preview_lookup ON public.sk_booking USING btree (id_campaign, id_site_sevice, service_date, init_interval_hour, end_interval_hour, resource_no, client_id) INCLUDE (id);

-- sk_booking: idx_sk_booking_time_slots
CREATE INDEX IF NOT EXISTS idx_sk_booking_time_slots ON public.sk_booking USING btree (id_site_sevice, id_campaign, service_date, init_interval_hour, end_interval_hour, resource_no);

-- sk_booking: sk_booking__date_time_id_idx
CREATE INDEX IF NOT EXISTS sk_booking__date_time_id_idx ON public.sk_booking USING btree (service_date, init_interval_hour, id);

-- sk_booking: sk_booking__site_sevice_date_time_idx
CREATE INDEX IF NOT EXISTS sk_booking__site_sevice_date_time_idx ON public.sk_booking USING btree (id_site_sevice, service_date, init_interval_hour);

-- sk_booking: new_booking_duplicate_pkey
CREATE UNIQUE INDEX IF NOT EXISTS new_booking_duplicate_pkey ON public.sk_booking USING btree (id);

-- sk_booking: sk_booking_site_campaign_date_idx
CREATE INDEX IF NOT EXISTS sk_booking_site_campaign_date_idx ON public.sk_booking USING btree (id_site_sevice, id_campaign, reserved, service_date);

-- sk_booking: idx_booking_overlap_check
CREATE INDEX IF NOT EXISTS idx_booking_overlap_check ON public.sk_booking USING btree (id_campaign, id_site_sevice, service_date, client_id) WHERE (service_date IS NOT NULL);

-- sk_booking: idx_sk_booking_id_campaign
CREATE INDEX IF NOT EXISTS idx_sk_booking_id_campaign ON public.sk_booking USING btree (id_campaign);

-- sk_booking: sk_booking_id_site_sevice_idx
CREATE INDEX IF NOT EXISTS sk_booking_id_site_sevice_idx ON public.sk_booking USING btree (id_site_sevice);

-- sk_booking: idx_multi_group
CREATE INDEX IF NOT EXISTS idx_multi_group ON public.sk_booking USING btree (id_site_sevice, id_campaign, ((details ->> 'multi_dose_group_id'::text)));

-- pet: pet_breed_gender_idx
CREATE INDEX IF NOT EXISTS pet_breed_gender_idx ON public.pet USING btree (breed_id, gender, id);

-- sk_routines: routines_pkey
CREATE UNIQUE INDEX IF NOT EXISTS routines_pkey ON public.sk_routines USING btree (id);

-- pet: pet_pkey
CREATE UNIQUE INDEX IF NOT EXISTS pet_pkey ON public.pet USING btree (id);

-- animal: animal_pkey
CREATE UNIQUE INDEX IF NOT EXISTS animal_pkey ON public.animal USING btree (animal_id);

-- dp_person_type: dp_person_type_pkey
CREATE UNIQUE INDEX IF NOT EXISTS dp_person_type_pkey ON public.dp_person_type USING btree (person_type_id);

-- cfg_system_page: sidebar_items_pkey
CREATE UNIQUE INDEX IF NOT EXISTS sidebar_items_pkey ON public.cfg_system_page USING btree (id);

-- sk_campaign: sk_campaign_client_id_id_idx
CREATE INDEX IF NOT EXISTS sk_campaign_client_id_id_idx ON public.sk_campaign USING btree (client_id, id);

-- attendant_type: attendant_type_pkey
CREATE UNIQUE INDEX IF NOT EXISTS attendant_type_pkey ON public.attendant_type USING btree (id);

-- breed: breed_pkey
CREATE UNIQUE INDEX IF NOT EXISTS breed_pkey ON public.breed USING btree (id);

-- breed: breed_id_specie_idx
CREATE INDEX IF NOT EXISTS breed_id_specie_idx ON public.breed USING btree (id_specie, id);

-- sk_sites_services: sites_services_duplicate_pkey
CREATE UNIQUE INDEX IF NOT EXISTS sites_services_duplicate_pkey ON public.sk_sites_services USING btree (id);

-- sk_sites_services: idx_site_service_active
CREATE INDEX IF NOT EXISTS idx_site_service_active ON public.sk_sites_services USING btree (id, client_id, active) WHERE (active = true);

-- sk_sites_services: idx_sk_sites_services_id_campaing
CREATE INDEX IF NOT EXISTS idx_sk_sites_services_id_campaing ON public.sk_sites_services USING btree (id_campaing);

-- aud_booking: idx_aud_booking_booking_id
CREATE INDEX IF NOT EXISTS idx_aud_booking_booking_id ON public.aud_booking USING btree (booking_id);

-- sk_booking: sk_booking_res_person_date_idx
CREATE INDEX IF NOT EXISTS sk_booking_res_person_date_idx ON public.sk_booking USING btree (id_beneficiary, service_date) WHERE ((reserved = true) AND (id_beneficiary IS NOT NULL));

-- sk_attendants: idx_sk_attendants_user_id_status
CREATE INDEX IF NOT EXISTS idx_sk_attendants_user_id_status ON public.sk_attendants USING btree (user_id, status);

-- trx_vaccine_application: idx_trx_vaccine_application_pet
CREATE INDEX IF NOT EXISTS idx_trx_vaccine_application_pet ON public.trx_vaccine_application USING btree (pet_id);

-- sk_booking: sk_booking_conflict_beneficiary_idx
CREATE INDEX IF NOT EXISTS sk_booking_conflict_beneficiary_idx ON public.sk_booking USING btree (id_site_sevice, id_beneficiary, service_date, init_interval_hour, end_interval_hour, resource_no) WHERE (reserved = true);

-- cfg_vaccine_batch_input: uq_cfg_vaccine_batch_input
CREATE UNIQUE INDEX IF NOT EXISTS uq_cfg_vaccine_batch_input ON public.cfg_vaccine_batch_input USING btree (client_id, id_site_service, id_vaccine, batch_number);

-- sk_booking: sk_booking__beneficiary_part_idx
CREATE INDEX IF NOT EXISTS sk_booking__beneficiary_part_idx ON public.sk_booking USING btree (id_beneficiary) WHERE (id_beneficiary IS NOT NULL);

-- sk_booking: idx_sk_booking_pet
CREATE INDEX IF NOT EXISTS idx_sk_booking_pet ON public.sk_booking USING btree (pet_id) WHERE (pet_id IS NOT NULL);

-- sk_booking: idx_sk_booking_group_key
CREATE INDEX IF NOT EXISTS idx_sk_booking_group_key ON public.sk_booking USING btree (id_beneficiary, group_key, service_date, reserved) WHERE (reserved = true);

-- ref_departments: ref_departments_pkey
CREATE UNIQUE INDEX IF NOT EXISTS ref_departments_pkey ON public.ref_departments USING btree (id);

-- cfg_service_department_status: cfg_service_department_status_pkey
CREATE UNIQUE INDEX IF NOT EXISTS cfg_service_department_status_pkey ON public.cfg_service_department_status USING btree (id);

-- cfg_departaments_status: cfg_departaments_status_pkey
CREATE UNIQUE INDEX IF NOT EXISTS cfg_departaments_status_pkey ON public.cfg_departaments_status USING btree (id);

-- person: person_pkey
CREATE UNIQUE INDEX IF NOT EXISTS person_pkey ON public.person USING btree (person_id);

-- master_vaccine: master_vaccine_pkey
CREATE UNIQUE INDEX IF NOT EXISTS master_vaccine_pkey ON public.master_vaccine USING btree (id);

-- sk_booking: sk_booking_res_date_site_time_idx
CREATE INDEX IF NOT EXISTS sk_booking_res_date_site_time_idx ON public.sk_booking USING btree (service_date, id_site_sevice, init_interval_hour, end_interval_hour) WHERE (reserved = true);

-- ref_vaccine_brand: ref_vaccine_brand_pkey
CREATE UNIQUE INDEX IF NOT EXISTS ref_vaccine_brand_pkey ON public.ref_vaccine_brand USING btree (id);

-- cfg_service_departments: cfg_service_departments_pkey
CREATE UNIQUE INDEX IF NOT EXISTS cfg_service_departments_pkey ON public.cfg_service_departments USING btree (id);

-- sk_sites: idx_sites_location_data
CREATE INDEX IF NOT EXISTS idx_sites_location_data ON public.sk_sites USING btree (id) INCLUDE (country, state, city);

-- sec_role_system_page: idx_sec_role_system_page_page_id
CREATE INDEX IF NOT EXISTS idx_sec_role_system_page_page_id ON public.sec_role_system_page USING btree (id_page);

-- sec_role_system_page: idx_sec_role_system_page_attendant_type_id
CREATE INDEX IF NOT EXISTS idx_sec_role_system_page_attendant_type_id ON public.sec_role_system_page USING btree (id_attendant_type);

-- sec_role_system_page: sec_role_system_page_attendant_page_key
CREATE UNIQUE INDEX IF NOT EXISTS sec_role_system_page_attendant_page_key ON public.sec_role_system_page USING btree (id_attendant_type, id_page);

-- sk_call_queue: ux_sk_call_queue_item
CREATE UNIQUE INDEX IF NOT EXISTS ux_sk_call_queue_item ON public.sk_call_queue USING btree (id_site_service, service_date, source_type, id_source);

-- sk_call_queue: sk_call_queue_service_date_idx
CREATE INDEX IF NOT EXISTS sk_call_queue_service_date_idx ON public.sk_call_queue USING btree (service_date);

-- sk_call_queue: sk_call_queue_pkey
CREATE UNIQUE INDEX IF NOT EXISTS sk_call_queue_pkey ON public.sk_call_queue USING btree (id);

-- sk_call_queue: sk_call_queue_id_source_key
CREATE UNIQUE INDEX IF NOT EXISTS sk_call_queue_id_source_key ON public.sk_call_queue USING btree (id_source);

-- sk_service: new_service_pkey
CREATE UNIQUE INDEX IF NOT EXISTS new_service_pkey ON public.sk_service USING btree (id);
