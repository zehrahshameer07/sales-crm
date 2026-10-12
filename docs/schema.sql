-- Sales CRM database schema 
CREATE TABLE activities (
	id INTEGER NOT NULL,
	customer_name VARCHAR(120) NOT NULL,
	contact VARCHAR(20),
	location VARCHAR(120),
	product_interested VARCHAR(30),
	activity_type VARCHAR(30) NOT NULL,
	status VARCHAR(30) NOT NULL,
	notes TEXT,
	start_date DATE NOT NULL,
	end_date DATE,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX ix_activities_created_at ON activities (created_at);
CREATE INDEX ix_activities_customer_name ON activities (customer_name);
CREATE INDEX ix_activities_id ON activities (id);
CREATE INDEX ix_activities_start_date ON activities (start_date);
CREATE INDEX ix_activities_status ON activities (status);