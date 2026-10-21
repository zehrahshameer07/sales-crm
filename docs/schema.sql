-- FreeBees Sales CRM: PostgreSQL schema (generated with pg_dump -s from the migrated database).
-- The app creates all of this automatically on startup via Alembic migrations (alembic/versions/0001_initial_schema.py).

\restrict kAOIqhwLtLVs5iAsiJ9MqqCdhWgZWJxRG7pmhx8KzIkEE1ekIt2mzqaihFcUfne

-- Name: public; Type: SCHEMA; Schema: -; Owner: -

-- *not* creating schema, since initdb creates it

-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -

COMMENT ON SCHEMA public IS '';

-- Name: activity_status; Type: TYPE; Schema: public; Owner: -

CREATE TYPE public.activity_status AS ENUM (
    'pending',
    'in_progress',
    'completed'
);

-- Name: activity_type; Type: TYPE; Schema: public; Owner: -

CREATE TYPE public.activity_type AS ENUM (
    'call',
    'visit',
    'demo',
    'follow_up'
);

-- Name: product; Type: TYPE; Schema: public; Owner: -

CREATE TYPE public.product AS ENUM (
    'freebees_menu',
    'freebees_play',
    'both'
);

-- Name: user_role; Type: TYPE; Schema: public; Owner: -

CREATE TYPE public.user_role AS ENUM (
    'admin',
    'manager',
    'salesperson'
);

-- Name: activities; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.activities (
    id uuid NOT NULL,
    owner_id uuid NOT NULL,
    customer_name character varying(120) NOT NULL,
    customer_key character varying(120) NOT NULL,
    activity_type public.activity_type NOT NULL,
    status public.activity_status NOT NULL,
    product_interested public.product,
    contact character varying(20),
    location character varying(120),
    notes text,
    start_date date NOT NULL,
    end_date date,
    follow_up_date date,
    follow_up_notes character varying(500),
    created_by_id uuid,
    updated_by_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_activities_ck_activities_end_after_start CHECK (((end_date IS NULL) OR (end_date >= start_date))),
    CONSTRAINT ck_activities_ck_activities_end_only_when_completed CHECK (((end_date IS NULL) OR (status = 'completed'::public.activity_status))),
    CONSTRAINT ck_activities_ck_activities_follow_up_after_start CHECK (((follow_up_date IS NULL) OR (follow_up_date >= start_date)))
);

    version_num character varying(32) NOT NULL
);

-- Name: status_history; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.status_history (
    id uuid NOT NULL,
    activity_id uuid NOT NULL,
    changed_by_id uuid,
    from_status public.activity_status,
    to_status public.activity_status NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL
);

-- Name: users; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.users (
    id uuid NOT NULL,
    full_name character varying(120) NOT NULL,
    email character varying(254) NOT NULL,
    phone character varying(20),
    password_hash character varying(255) NOT NULL,
    role public.user_role NOT NULL,
    manager_id uuid,
    designation character varying(80),
    region character varying(80),
    employee_code character varying(30),
    is_active boolean DEFAULT true NOT NULL,
    must_change_password boolean DEFAULT false NOT NULL,
    failed_login_attempts integer DEFAULT 0 NOT NULL,
    locked_until timestamp with time zone,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- Name: activities pk_activities; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT pk_activities PRIMARY KEY (id);

-- Name: status_history pk_status_history; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.status_history
    ADD CONSTRAINT pk_status_history PRIMARY KEY (id);

-- Name: users pk_users; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);

-- Name: activities uq_activities_no_duplicates; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT uq_activities_no_duplicates UNIQUE (owner_id, customer_key, activity_type, start_date);

-- Name: users uq_users_employee_code; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_employee_code UNIQUE (employee_code);

-- Name: ix_activities_follow_up_date; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_activities_follow_up_date ON public.activities USING btree (follow_up_date);

-- Name: ix_activities_owner_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_activities_owner_id ON public.activities USING btree (owner_id);

-- Name: ix_activities_owner_id_start_date; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_activities_owner_id_start_date ON public.activities USING btree (owner_id, start_date);

-- Name: ix_activities_start_date; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_activities_start_date ON public.activities USING btree (start_date);

-- Name: ix_activities_status; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_activities_status ON public.activities USING btree (status);

-- Name: ix_status_history_activity_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_status_history_activity_id ON public.status_history USING btree (activity_id);

-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);

-- Name: ix_users_manager_id; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_users_manager_id ON public.users USING btree (manager_id);

-- Name: ix_users_role; Type: INDEX; Schema: public; Owner: -

CREATE INDEX ix_users_role ON public.users USING btree (role);

-- Name: activities fk_activities_created_by_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT fk_activities_created_by_id_users FOREIGN KEY (created_by_id) REFERENCES public.users(id) ON DELETE SET NULL;

-- Name: activities fk_activities_owner_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT fk_activities_owner_id_users FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE RESTRICT;

-- Name: activities fk_activities_updated_by_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT fk_activities_updated_by_id_users FOREIGN KEY (updated_by_id) REFERENCES public.users(id) ON DELETE SET NULL;

-- Name: status_history fk_status_history_activity_id_activities; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.status_history
    ADD CONSTRAINT fk_status_history_activity_id_activities FOREIGN KEY (activity_id) REFERENCES public.activities(id) ON DELETE CASCADE;

-- Name: status_history fk_status_history_changed_by_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.status_history
    ADD CONSTRAINT fk_status_history_changed_by_id_users FOREIGN KEY (changed_by_id) REFERENCES public.users(id) ON DELETE SET NULL;

-- Name: users fk_users_manager_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_manager_id_users FOREIGN KEY (manager_id) REFERENCES public.users(id) ON DELETE SET NULL;

\unrestrict kAOIqhwLtLVs5iAsiJ9MqqCdhWgZWJxRG7pmhx8KzIkEE1ekIt2mzqaihFcUfne
