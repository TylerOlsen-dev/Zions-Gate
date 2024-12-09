-- Remove all users from the database

SET sql_safe_updates = 0;
DELETE from users;
SET sql_safe_updates = 1;

-- Remove specific user from the database

DELETE
FROM users
WHERE discord_id = ;


-- Pull the username and ID of the person who most recently joined

SELECT username, time_created
FROM users
ORDER BY time_created DESC
LIMIT 1;


-- Pull the username and ID of the person who most was most recently verified

SELECT * 
FROM discord_verification.users
WHERE verify_status = 1
ORDER BY time_created DESC
LIMIT 1;


-- Pull all usernames banned in the last 5 minutes

SELECT 
    users.username,
    global_bans.discord_id,
    global_bans.banned_at,
    global_bans.reason
FROM users
JOIN global_bans
ON users.discord_id = global_bans.discord_id
WHERE global_bans.banned_at >= DATE_SUB(NOW(), INTERVAL 5 MINUTE);

