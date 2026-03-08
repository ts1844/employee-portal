CREATE DATABASE employee_portal;
USE employee_portal;

CREATE TABLE employees( id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100), email VARCHAR(100), password VARCHAR(100), role VARCHAR(20));


#for testing
INSERT INTO employees(email,password) VALUES("employee@gmail.com","1234");
INSERT INTO employees(email,password,role) VALUES ('manager@company.com','admin123','manager');
UPDATE employees SET role = "employee" WHERE id = 1;

# Attendance
CREATE TABLE attendance( id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(100), date DATE, time TIME );

# Work Log
CREATE TABLE worklog( id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(100), work TEXT, date DATE, time TIME);

#check 
SELECT * FROM attendance;
SELECT * FROM worklog;
SELECT * FROM employees;
