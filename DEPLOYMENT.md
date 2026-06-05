# 小红书客服平台 - 部署文档

## 环境信息
- **操作系统**: Amazon Linux 2 (EC2)
- **内核**: 5.10.234-225.921.amzn2.x86_64
- **架构**: x86_64

---

## ⚠️ 重要提示

### 问题1: Node.js 版本太老
服务器默认 Node.js 版本不支持 `??=` 语法（需要 Node ≥ 15）。

**解决方案**: **不要在服务器上跑 `npm run dev` 或 `npm run build`**！
- ✅ 在本地机器构建前端：`npm run build`
- ✅ 上传 `dist/` 目录到服务器，用 nginx 托管静态文件

### 问题2: Python 依赖安装失败
`requirements.txt` 可能有拼写错误。

**解决方案**: 已修正 `requirements.txt`，请确保使用修正后的版本。

---

## 🚀 完整部署步骤

### 第一步：本地准备

```bash
# 1. 本地构建前端
cd /Users/luojianwei/WorkBuddy/20260411104248/customer-service-platform
npm install --legacy-peer-deps
npm run build

# 2. 确认 requirements.txt 已修正
cat backend/requirements.txt | grep -i langchain
# 应该显示正确的包名（如 langchain-community）
```

---

### 第二步：上传文件到服务器

```bash
# 1. 上传前端构建产物
scp -r frontend/dist/* ec2-user@your-server-ip:/var/www/html/customer-service/

# 2. 上传后端代码
scp -r backend ec2-user@your-server-ip:/opt/customer-service-platform/

# 3. 上传部署脚本和配置文件
scp deploy-backend.sh ec2-user@your-server-ip:/opt/customer-service-platform/
scp nginx-customer-service.conf ec2-user@your-server-ip:/tmp/
```

---

### 第三步：服务器上配置 nginx

```bash
# 1. 安装 nginx（如果未安装）
sudo amazon-linux-extras install nginx1 -y

# 2. 复制配置文件
sudo cp /tmp/nginx-customer-service.conf /etc/nginx/conf.d/customer-service.conf

# 3. 修改配置文件的 server_name
sudo vi /etc/nginx/conf.d/customer-service.conf
# 将 `server_name your-domain.com;` 改为你的域名或 IP

# 4. 测试配置
sudo nginx -t

# 5. 重启 nginx
sudo systemctl enable nginx
sudo systemctl restart nginx
```

---

### 第四步：服务器上部署后端

```bash
# 1. 登录服务器
ssh ec2-user@your-server-ip

# 2. 进入项目目录
cd /opt/customer-service-platform

# 3. 运行部署脚本（需要 sudo）
sudo ./deploy-backend.sh

# 4. 检查服务状态
sudo systemctl status customer-service-backend

# 5. 查看日志
sudo journalctl -u customer-service-backend -f
```

---

### 第五步：验证部署

```bash
# 1. 检查后端是否正常运行
curl http://localhost:8000/docs

# 2. 检查前端是否可访问
curl http://your-server-ip/

# 3. 检查 API 代理是否正常工作
curl http://your-server-ip/api/health
```

---

## 🔧 一键部署脚本（可选）

### 本地一键部署前端

```bash
# 修改脚本中的服务器 IP 和用户名
vi deploy-frontend.sh

# 运行脚本
chmod +x deploy-frontend.sh
./deploy-frontend.sh your-server-ip ec2-user
```

---

## 📋 常见问题排查

### 1. 前端页面空白
- 检查 nginx 配置：`sudo nginx -t`
- 检查前端文件路径：`ls -la /var/www/html/customer-service/`
- 查看 nginx 日志：`sudo tail -f /var/log/nginx/error.log`

### 2. 后端无法启动
- 检查 Python 版本：`python3 --version`（需要 3.8+）
- 检查虚拟环境：`ls -la /opt/customer-service-platform/backend/venv/`
- 查看服务日志：`sudo journalctl -u customer-service-backend -n 50`

### 3. API 请求失败
- 检查后端是否运行：`curl http://localhost:8000/docs`
- 检查 nginx 代理配置：`cat /etc/nginx/conf.d/customer-service.conf`
- 检查防火墙：`sudo iptables -L -n`

### 4. WebSocket 连接失败
- 检查 nginx 配置中的 `/ws/` 路径
- 确保 `proxy_http_version 1.1;` 已设置
- 确保 `Upgrade` 和 `Connection` 头已设置

---

## 🔄 更新部署

### 前端更新

```bash
# 本地重新构建
cd frontend
npm run build

# 上传到服务器
scp -r dist/* ec2-user@your-server-ip:/var/www/html/customer-service/

# 重载 nginx（可选）
ssh ec2-user@your-server-ip "sudo systemctl reload nginx"
```

### 后端更新

```bash
# 上传新代码到服务器
scp -r backend/*.py ec2-user@your-server-ip:/opt/customer-service-platform/backend/

# 重启后端服务
ssh ec2-user@your-server-ip "sudo systemctl restart customer-service-backend"
```

---

## 📊 监控和维护

### 查看服务状态

```bash
# 后端服务
sudo systemctl status customer-service-backend

# nginx 服务
sudo systemctl status nginx

# 查看进程
ps aux | grep uvicorn
ps aux | grep nginx
```

### 查看日志

```bash
# 后端日志
sudo journalctl -u customer-service-backend -f

# nginx 访问日志
sudo tail -f /var/log/nginx/access.log

# nginx 错误日志
sudo tail -f /var/log/nginx/error.log
```

### 重启服务

```bash
# 重启后端
sudo systemctl restart customer-service-backend

# 重启 nginx
sudo systemctl restart nginx
```

---

## 🔐 安全建议

1. **使用 HTTPS**：配置 Let's Encrypt 免费证书
   ```bash
   sudo amazon-linux-extras install epel -y
   sudo yum install certbot python2-certbot-nginx -y
   sudo certbot --nginx -d your-domain.com
   ```

2. **配置防火墙**：只开放 80/443 端口
   ```bash
   sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
   sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
   sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
   sudo iptables -A INPUT -j DROP
   ```

3. **定期更新系统**：
   ```bash
   sudo yum update -y
   ```

---

## 📞 技术支持

如遇到部署问题，请检查：
1. 日志文件（`journalctl`、`/var/log/nginx/`）
2. 服务状态（`systemctl status`）
3. 网络连接（`curl`、`ping`）

---

**部署完成！🎉**
