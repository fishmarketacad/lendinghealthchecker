module.exports = {
  apps: [{
    name: 'lendinghealthchecker',
    script: 'lendinghealthchecker.py',
    interpreter: 'venv/bin/python',
    cwd: '/root/monadlendinghealthchecker',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      NODE_ENV: 'production'
    },
    // Logging configuration
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    error_file: '/root/monadlendinghealthchecker/logs/error.log',
    out_file: '/root/monadlendinghealthchecker/logs/app.log',
    log_file: '/root/monadlendinghealthchecker/logs/combined.log',
    merge_logs: true,
    log_type: 'json',
    
    // Log rotation (PM2 built-in)
    max_size: '10M',      // Max log file size before rotation
    retain: 5,            // Keep 5 rotated log files
    compress: true,       // Compress rotated logs
    
    // Restart policy
    min_uptime: '10s',
    max_restarts: 10,
    restart_delay: 4000,
    
    // Cron restart (optional - restart daily at 3 AM UTC)
    // cron_restart: '0 3 * * *',
    
    // Kill timeout
    kill_timeout: 5000
  }]
};

