require('dotenv').config();
const { Client, GatewayIntentBits, Partials } = require('discord.js');
const mysql = require('mysql2/promise');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

const BAN_WEBHOOK_URL = process.env.BAN_WEBHOOK_URL;
const AVATAR_WEBHOOK_URL = process.env.AVATAR_WEBHOOK_URL;
const REPORT_WEBHOOK_URL = process.env.REPORT_WEBHOOK_URL;
const LK_WEBHOOK_URL = process.env.LK_WEBHOOK_URL;
const LB_WEBHOOK_URL = process.env.LB_WEBHOOK_URL;
const PURGE_WEBHOOK_URL = process.env.PURGE_WEBHOOK_URL;
const BOT_TOKEN = process.env.BOT_TOKEN;

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMembers, GatewayIntentBits.MessageContent],
});

async function dbConnection() {
  return await mysql.createConnection({
    host: process.env.DB_HOST,
    user: process.env.DB_USER,
    password: process.env.DB_PASS,
    database: process.env.DB_NAME,
  });
}

// Server Registration
async function registerServer(guild) {
  try {
    const connection = await dbConnection();
    const [rows] = await connection.execute("SELECT Guild_ID FROM servers WHERE Guild_ID = ?", [guild.id]);
    if (rows.length === 0) {
      await connection.execute("INSERT INTO servers (Guild_ID, Server_Name, OwnerID, setup) VALUES (?, ?, 0, FALSE)", [guild.id, guild.name]);
      console.log(`Registered server: ${guild.name} (ID: ${guild.id})`);
    }
    await connection.end();
  } catch (err) {
    console.error("Error registering server:", err);
  }
}

// Global Check for Server Setup
async function checkServerSetup(interaction) {
  if (interaction.commandName === "setup") return true;
  const guild = interaction.guild;
  if (!guild) return true;
  try {
    const connection = await dbConnection();
    const [rows] = await connection.execute("SELECT setup FROM servers WHERE Guild_ID = ?", [guild.id]);
    await connection.end();
    if (rows.length > 0 && (rows[0].setup === 1 || rows[0].setup === true)) {
      return true;
    } else {
      if (!interaction.replied) {
        await interaction.reply({ content: "Access Denied: This server needs to be set up first. Run /setup", ephemeral: true });
      } else {
        await interaction.followUp({ content: "Access Denied: This server needs to be set up first. Run /setup", ephemeral: true });
      }
      return false;
    }
  } catch (err) {
    console.error("Error checking server setup:", err);
    if (!interaction.replied) {
      await interaction.reply({ content: "Server setup check failed. Run /setup", ephemeral: true });
    } else {
      await interaction.followUp({ content: "Server setup check failed. Run /setup", ephemeral: true });
    }
    return false;
  }
}

// Command Role Check
async function checkCommandRoles(interaction) {
  const restrictedCommands = ["localkick", "localban", "globalban", "globalunban"];
  if (!restrictedCommands.includes(interaction.commandName.toLowerCase())) return true;
  const guild = interaction.guild;
  if (!guild) return true;
  let allowedRoles = [];
  try {
    const connection = await dbConnection();
    let [rows] = [];
    if (["globalban", "globalunban"].includes(interaction.commandName.toLowerCase())) {
      [rows] = await connection.execute("SELECT Global_1, Global_2, Global_3 FROM servers WHERE Guild_ID = ?", [guild.id]);
      if (rows.length > 0) {
        allowedRoles = Object.values(rows[0]).filter(r => r !== null);
      }
    } else if (["localkick", "localban"].includes(interaction.commandName.toLowerCase())) {
      let [localRows] = await connection.execute("SELECT Local_1, Local_2, Local_3 FROM servers WHERE Guild_ID = ?", [guild.id]);
      let [globalRows] = await connection.execute("SELECT Global_1, Global_2, Global_3 FROM servers WHERE Guild_ID = ?", [guild.id]);
      if (localRows.length > 0) {
        allowedRoles = allowedRoles.concat(Object.values(localRows[0]).filter(r => r !== null));
      }
      if (globalRows.length > 0) {
        allowedRoles = allowedRoles.concat(Object.values(globalRows[0]).filter(r => r !== null));
      }
    }
    await connection.end();
  } catch (err) {
    console.error("Error retrieving command roles:", err);
    throw new Error("Access Denied: Could not verify your permissions.");
  }
  const userRoleIds = interaction.member.roles.cache.map(role => role.id);
  if (allowedRoles.some(r => userRoleIds.includes(String(r)))) {
    return true;
  } else {
    throw new Error("Access Denied: You do not have permission to use this command.");
  }
}

// Combined Global Check
async function combinedCheck(interaction) {
  try {
    if (!(await checkServerSetup(interaction))) return false;
    if (!(await checkCommandRoles(interaction))) return false;
    return true;
  } catch (err) {
    try {
      if (!interaction.replied) {
        await interaction.reply({ content: String(err), ephemeral: true });
      } else {
        await interaction.followUp({ content: String(err), ephemeral: true });
      }
    } catch (error) {
      console.error("Error sending combined check error message:", error);
    }
    return false;
  }
}

// Database Utility Functions
async function addMemberToUsers(member) {
  if (member.user.bot) return;
  const user_id = member.id;
  const user_name = `${member.user.username}#${member.user.discriminator}`;
  const account_age = member.user.createdAt.toISOString().slice(0, 10);
  try {
    const connection = await dbConnection();
    const [rows] = await connection.execute("SELECT User_ID FROM Users WHERE User_ID = ?", [user_id]);
    if (rows.length === 0) {
      await connection.execute("INSERT INTO Users (User_ID, User_Name, Account_Age, Global_Banned) VALUES (?, ?, ?, ?)", [user_id, user_name, account_age, "False"]);
      console.log(`Added new user: ${user_name} (ID: ${user_id}) to Users table.`);
    }
    await connection.end();
  } catch (err) {
    console.error("Database error:", err);
  }
}

async function setGlobalBan(userId, banned) {
  try {
    const connection = await dbConnection();
    const value = banned ? "True" : "False";
    await connection.execute("UPDATE Users SET Global_Banned = ? WHERE User_ID = ?", [value, userId]);
    await connection.end();
  } catch (err) {
    console.error("Database error:", err);
  }
}

async function isGloballyBanned(userId) {
  try {
    const connection = await dbConnection();
    const [rows] = await connection.execute("SELECT Global_Banned FROM Users WHERE User_ID = ?", [userId]);
    await connection.end();
    return rows.length > 0 && rows[0].Global_Banned === "True";
  } catch (err) {
    console.error("Database error:", err);
    return false;
  }
}

// On Member Join
client.on("guildMemberAdd", async (member) => {
  try {
    const connection = await dbConnection();
    const [rows] = await connection.execute("SELECT setup FROM servers WHERE Guild_ID = ?", [member.guild.id]);
    await connection.end();
    if (rows.length > 0 && (rows[0].setup === 1 || rows[0].setup === true || rows[0].setup === "True")) {
      await addMemberToUsers(member);
      if (await isGloballyBanned(member.id)) {
        try {
          await member.guild.members.ban(member, { reason: "Global ban active." });
          console.log(`Banned ${member.user.tag} from ${member.guild.name} due to global ban.`);
        } catch (err) {
          console.error(`Error banning ${member.user.tag} in ${member.guild.name}:`, err);
        }
      }
    } else {
      console.log(`Server ${member.guild.name} is not set up; not adding ${member.user.tag} to Users table.`);
    }
  } catch (err) {
    console.error("Error checking server setup on member join:", err);
  }
});

// Interaction Handler
client.on("interactionCreate", async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  if (!(await combinedCheck(interaction))) return;
  try {
    switch (interaction.commandName) {
      case "setup":
        {
          const { guild } = interaction;
          if (!guild) {
            await interaction.reply({ content: "This command can only be used in a guild.", ephemeral: true });
            return;
          }
          await registerServer(guild);
          const connection = await dbConnection();
          const [rows] = await connection.execute("SELECT OwnerID FROM servers WHERE Guild_ID = ?", [guild.id]);
          await connection.end();
          if (rows.length === 0 || Number(rows[0].OwnerID) === 0) {
            await interaction.reply({ content: "Access Denied: Server owner not registered. Please contact the bot admin.", ephemeral: true });
            return;
          }
          if (interaction.user.id !== String(rows[0].OwnerID)) {
            await interaction.reply({ content: "Access Denied: Only the registered server owner can run this command.", ephemeral: true });
            return;
          }
          const local1 = interaction.options.getRole("local1");
          const global1 = interaction.options.getRole("global1");
          const local2 = interaction.options.getRole("local2");
          const local3 = interaction.options.getRole("local3");
          const global2 = interaction.options.getRole("global2");
          const global3 = interaction.options.getRole("global3");
          const conn = await dbConnection();
          await conn.execute(
            "UPDATE servers SET Server_Name = ?, Local_1 = ?, Local_2 = ?, Local_3 = ?, Global_1 = ?, Global_2 = ?, Global_3 = ?, setup = TRUE WHERE Guild_ID = ?",
            [guild.name, local1.id, local2 ? local2.id : null, local3 ? local3.id : null, global1.id, global2 ? global2.id : null, global3 ? global3.id : null, guild.id]
          );
          await conn.end();
          guild.members.cache.forEach(async (member) => {
            await addMemberToUsers(member);
          });
          await interaction.reply({ content: "Server setup complete. Command access is now enabled.", ephemeral: true });
        }
        break;
      case "globalban":
        {
          const user = interaction.options.getUser("user");
          const reason = interaction.options.getString("reason");
          await setGlobalBan(user.id, true);
          let bannedIn = [];
          for (const guild of client.guilds.cache.values()) {
            const member = guild.members.cache.get(user.id);
            if (member) {
              try {
                await guild.members.ban(member, { reason });
                bannedIn.push(guild.name);
              } catch (err) {
                console.error(`Failed to ban ${user.tag} in ${guild.name}:`, err);
              }
            }
          }
          const webhookMessage = `**Global Ban executed for ${user.tag} (ID: ${user.id}).**\n**Reason:** ${reason}\n\nPlease reply with screenshots of evidence supporting this ban.`;
          await axios.post(BAN_WEBHOOK_URL, { content: webhookMessage });
          await interaction.reply({ content: `Globally banned ${user} from: ${bannedIn.join(", ")}. Database updated.`, ephemeral: true });
        }
        break;
      case "globalunban":
        {
          const user = interaction.options.getUser("user");
          await setGlobalBan(user.id, false);
          let unbannedIn = [];
          for (const guild of client.guilds.cache.values()) {
            try {
              await guild.members.unban(user, "Global unban command issued.");
              unbannedIn.push(guild.name);
            } catch (err) {
              // Ignore if not banned
            }
          }
          const webhookMessage = `**Global Unban executed for ${user.tag} (ID: ${user.id}).**\n**Executed by:** ${interaction.user.tag} (ID: ${interaction.user.id}).\n**Guilds affected:** ${unbannedIn.length > 0 ? unbannedIn.join(", ") : "None"}.`;
          await axios.post(BAN_WEBHOOK_URL, { content: webhookMessage });
          await interaction.reply({ content: `Global unban executed for ${user} from: ${unbannedIn.join(", ")}. Database updated.`, ephemeral: true });
        }
        break;
      case "reportuser":
        {
          const user = interaction.options.getUser("user");
          const reason = interaction.options.getString("reason");
          const location = interaction.options.getString("location");
          const reportMessage = `**User Report Received**\n\n**Reported User:** ${user.tag} (ID: ${user.id})\n**Reported By:** ${interaction.user.tag} (ID: ${interaction.user.id})\n**Location:** ${location}\n**Reason:** ${reason}`;
          await axios.post(REPORT_WEBHOOK_URL, { content: reportMessage });
          await interaction.reply({ content: "Your report has been submitted. Moderators or administrators will review your report and may contact you for further details.", ephemeral: true });
        }
        break;
      case "localkick":
        {
          const member = interaction.options.getMember("user");
          const reason = interaction.options.getString("reason");
          try {
            await interaction.guild.members.kick(member, reason);
            const webhookMessage = `**Local Kick executed for ${member.user.tag} (ID: ${member.id}) in ${interaction.guild.name}.**\n**Reason:** ${reason}\n\nPlease reply with screenshots of evidence supporting this kick.`;
            await axios.post(LK_WEBHOOK_URL, { content: webhookMessage });
            await interaction.reply({ content: `Locally kicked ${member} from ${interaction.guild.name}.`, ephemeral: true });
          } catch (err) {
            await interaction.reply({ content: `Error kicking user: ${err}`, ephemeral: true });
          }
        }
        break;
      case "localban":
        {
          const member = interaction.options.getMember("user");
          const reason = interaction.options.getString("reason");
          try {
            await interaction.guild.members.ban(member, { reason });
            const webhookMessage = `**Local Ban executed for ${member.user.tag} (ID: ${member.id}) in ${interaction.guild.name}.**\n**Reason:** ${reason}\n\nPlease reply with screenshots of evidence supporting this ban.`;
            await axios.post(LB_WEBHOOK_URL, { content: webhookMessage });
            await interaction.reply({ content: `Locally banned ${member} from ${interaction.guild.name}.`, ephemeral: true });
          } catch (err) {
            await interaction.reply({ content: `Error banning user: ${err}`, ephemeral: true });
          }
        }
        break;
      case "purge":
        {
          const channel = interaction.options.getChannel("channel");
          const limit = interaction.options.getInteger("limit");
          if (limit <= 0 || limit > 1000) {
            await interaction.reply({ content: "Please specify a limit between 1 and 1000.", ephemeral: true });
            return;
          }
          await interaction.reply({ content: `Purging ${limit} messages from ${channel}.`, ephemeral: true });
          const deletedMessages = await channel.bulkDelete(limit, true);
          const logFilename = `purged_messages_${new Date().toISOString().replace(/[:\-\.]/g, "")}.csv`;
          const csvLines = ["Timestamp,Author,Author ID,Content"];
          deletedMessages.forEach(msg => {
            const line = `${msg.createdAt.toISOString().slice(0,19).replace("T", " ")},${msg.author.tag},${msg.author.id},"${msg.content.replace(/\n/g, "\\n")}"`;
            csvLines.push(line);
          });
          fs.writeFileSync(logFilename, csvLines.join("\n"), "utf-8");
          if (PURGE_WEBHOOK_URL) {
            try {
              const FormData = require('form-data');
              const form = new FormData();
              form.append("content", `Purged ${deletedMessages.size} messages from ${channel}. Log file attached:`);
              form.append("file", fs.createReadStream(path.join(__dirname, logFilename)), { filename: logFilename, contentType: "text/csv" });
              await axios.post(PURGE_WEBHOOK_URL, form, { headers: form.getHeaders() });
            } catch (err) {
              console.error("Error sending log file to the purge webhook:", err);
            }
          } else {
            console.log("Purge webhook URL not set. Log file was not sent.");
          }
          fs.unlinkSync(logFilename);
        }
        break;
      default:
        await interaction.reply({ content: "Unknown command", ephemeral: true });
    }
  } catch (err) {
    console.error("Error handling interaction:", err);
    if (!interaction.replied) {
      await interaction.reply({ content: "An error occurred while processing your command.", ephemeral: true });
    }
  }
});

// On User Update (Avatar Change)
client.on("userUpdate", async (before, after) => {
  if (before.avatar !== after.avatar) {
    const newAvatarUrl = after.avatarURL();
    const message = `${after.username}#${after.discriminator} changed their profile picture.`;
    const embed = { description: message, image: { url: newAvatarUrl } };
    try {
      await axios.post(AVATAR_WEBHOOK_URL, { content: message, embeds: [embed] });
    } catch (err) {
      console.error("Error sending avatar update webhook:", err);
    }
  }
});

// On Ready
client.once("ready", async () => {
  console.log(`Bot logged in as ${client.user.tag}`);
  try {
    await client.application.commands.set([]); // Clear commands if needed
    console.log("Slash commands cleared.");
  } catch (err) {
    console.error("Error clearing commands:", err);
  }
  for (const guild of client.guilds.cache.values()) {
    console.log(`Checking members in guild: ${guild.name}`);
    try {
      await registerServer(guild);
    } catch (err) {
      console.error("Error auto-registering server:", err);
    }
    try {
      const connection = await dbConnection();
      const [rows] = await connection.execute("SELECT setup FROM servers WHERE Guild_ID = ?", [guild.id]);
      await connection.end();
      if (rows.length > 0 && (rows[0].setup === 1 || rows[0].setup === true || rows[0].setup === "True")) {
        guild.members.cache.forEach(async (member) => {
          await addMemberToUsers(member);
        });
      } else {
        console.log(`Server ${guild.name} is not set up; not adding members to Users table.`);
      }
    } catch (err) {
      console.error(`Error checking setup for guild ${guild.name}:`, err);
    }
  }
});

client.login(BOT_TOKEN);