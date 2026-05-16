-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: localhost    Database: speakcv
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `company_questions`
--

DROP TABLE IF EXISTS `company_questions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `company_questions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `company_name` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `position` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `question_text` text COLLATE utf8mb4_unicode_ci,
  `difficulty` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `submitted_by` int DEFAULT NULL,
  `is_approved` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `submitted_by` (`submitted_by`),
  KEY `ix_company_questions_company_name` (`company_name`),
  KEY `ix_company_questions_id` (`id`),
  KEY `ix_company_questions_is_approved` (`is_approved`),
  CONSTRAINT `company_questions_ibfk_1` FOREIGN KEY (`submitted_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `company_questions`
--

LOCK TABLES `company_questions` WRITE;
/*!40000 ALTER TABLE `company_questions` DISABLE KEYS */;
INSERT INTO `company_questions` VALUES (1,'FPT','Frontend','Bạn xử lý sao nếu người dùng liên tục reload lại trang khiến trang giật lag','medium',1,1,'2026-03-17 20:39:29'),(2,'FPT Software','Frontend Developer','Giải thích sự khác nhau giữa Virtual DOM và Real DOM trong React?','medium',NULL,1,'2026-03-17 20:39:54'),(3,'FPT Software','Frontend Developer','Bạn xử lý state management trong ứng dụng React lớn như thế nào? So sánh Redux vs Context API.','medium',NULL,1,'2026-03-17 20:39:54'),(4,'FPT Software','Backend Developer','Giải thích RESTful API và các nguyên tắc thiết kế API tốt.','easy',NULL,1,'2026-03-17 20:39:54'),(5,'FPT Software','Backend Developer','Bạn xử lý database migration trong dự án thực tế như thế nào?','medium',NULL,1,'2026-03-17 20:39:54'),(6,'FPT Software','Fullstack Developer','Mô tả kiến trúc microservices. Khi nào nên dùng monolith vs microservices?','hard',NULL,1,'2026-03-17 20:39:54'),(7,'VNG Corporation','Backend Engineer','Thiết kế hệ thống chat real-time cho 1 triệu người dùng đồng thời.','hard',NULL,1,'2026-03-17 20:39:54'),(8,'VNG Corporation','Backend Engineer','Giải thích cách hoạt động của message queue (RabbitMQ/Kafka). Khi nào dùng?','medium',NULL,1,'2026-03-17 20:39:54'),(9,'VNG Corporation','Data Engineer','Sự khác nhau giữa SQL và NoSQL? Khi nào chọn MongoDB thay vì PostgreSQL?','medium',NULL,1,'2026-03-17 20:39:54'),(10,'VNG Corporation','Game Developer','Giải thích về game loop và cách tối ưu rendering performance.','hard',NULL,1,'2026-03-17 20:39:54'),(11,'Shopee','Software Engineer','Cho mảng số nguyên, tìm hai phần tử có tổng bằng target. Phân tích time/space complexity.','medium',NULL,1,'2026-03-17 20:39:54'),(12,'Shopee','Software Engineer','Thiết kế hệ thống URL shortener (như bit.ly) có thể xử lý 100 triệu URL.','hard',NULL,1,'2026-03-17 20:39:54'),(13,'Shopee','Frontend Engineer','Làm thế nào để tối ưu performance cho trang e-commerce có hàng ngàn sản phẩm?','medium',NULL,1,'2026-03-17 20:39:54'),(14,'Shopee','Backend Engineer','Giải thích caching strategies: Cache-aside, Write-through, Write-behind. Khi nào dùng Redis?','hard',NULL,1,'2026-03-17 20:39:54'),(15,'Tiki','Software Engineer','Thiết kế hệ thống thanh toán an toàn cho sàn e-commerce.','hard',NULL,1,'2026-03-17 20:39:54'),(16,'Tiki','Frontend Developer','Giải thích Server-Side Rendering (SSR) vs Client-Side Rendering (CSR). Next.js xử lý như thế nào?','medium',NULL,1,'2026-03-17 20:39:54'),(17,'Tiki','QA Engineer','Bạn viết test case cho chức năng \'Thêm sản phẩm vào giỏ hàng\' như thế nào?','easy',NULL,1,'2026-03-17 20:39:54'),(18,'Grab','Backend Engineer','Thiết kế hệ thống matching tài xế - khách hàng real-time.','hard',NULL,1,'2026-03-17 20:39:54'),(19,'Grab','Mobile Developer','So sánh React Native vs Flutter. Ưu nhược điểm của từng framework?','medium',NULL,1,'2026-03-17 20:39:54'),(20,'Grab','Data Scientist','Giải thích thuật toán surge pricing. Làm sao để tránh bias trong mô hình ML?','hard',NULL,1,'2026-03-17 20:39:54'),(21,'MoMo','Backend Developer','Giải thích ACID trong database transactions. Khi nào cần distributed transactions?','medium',NULL,1,'2026-03-17 20:39:54'),(22,'MoMo','Security Engineer','Các phương pháp bảo mật cho ứng dụng fintech: JWT, OAuth2, mã hóa dữ liệu.','hard',NULL,1,'2026-03-17 20:39:54'),(23,'MoMo','Frontend Developer','Bạn implement form validation phức tạp (CMND, số điện thoại, OTP) như thế nào?','easy',NULL,1,'2026-03-17 20:39:54'),(24,'VNPAY','Java Developer','Giải thích Spring Boot dependency injection. IoC container hoạt động như thế nào?','medium',NULL,1,'2026-03-17 20:39:54'),(25,'VNPAY','DevOps Engineer','Mô tả CI/CD pipeline cho ứng dụng Java. Docker, Kubernetes có vai trò gì?','medium',NULL,1,'2026-03-17 20:39:54'),(26,'Samsung Vietnam','Embedded Engineer','Giải thích sự khác nhau giữa process và thread. Deadlock xảy ra khi nào?','medium',NULL,1,'2026-03-17 20:39:54'),(27,'Samsung Vietnam','AI Engineer','So sánh CNN vs RNN. Khi nào dùng Transformer thay vì LSTM?','hard',NULL,1,'2026-03-17 20:39:54'),(28,'KMS Technology','Automation Tester','So sánh Selenium vs Cypress. Page Object Model pattern là gì?','medium',NULL,1,'2026-03-17 20:39:54'),(29,'KMS Technology','Fullstack Developer','Giải thích SOLID principles. Cho ví dụ vi phạm và cách sửa.','medium',NULL,1,'2026-03-17 20:39:54'),(30,'Startup Việt Nam','Intern/Junior','Kể về một dự án bạn tự hào nhất. Bạn gặp khó khăn gì và giải quyết ra sao?','easy',NULL,1,'2026-03-17 20:39:54'),(31,'Startup Việt Nam','Intern/Junior','Bạn học một công nghệ mới như thế nào? Cho ví dụ cụ thể.','easy',NULL,1,'2026-03-17 20:39:54');
/*!40000 ALTER TABLE `company_questions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `educations`
--

DROP TABLE IF EXISTS `educations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `educations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `school_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `degree` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `major` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_educations_user_id` (`user_id`),
  KEY `ix_educations_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `educations`
--

LOCK TABLES `educations` WRITE;
/*!40000 ALTER TABLE `educations` DISABLE KEYS */;
/*!40000 ALTER TABLE `educations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `experiences`
--

DROP TABLE IF EXISTS `experiences`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `experiences` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `company_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `position` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `is_current` tinyint(1) DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `ix_experiences_user_id` (`user_id`),
  KEY `ix_experiences_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `experiences`
--

LOCK TABLES `experiences` WRITE;
/*!40000 ALTER TABLE `experiences` DISABLE KEYS */;
/*!40000 ALTER TABLE `experiences` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `interview_history`
--

DROP TABLE IF EXISTS `interview_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `interview_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `position` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `score` float DEFAULT NULL,
  `overall_feedback` text COLLATE utf8mb4_unicode_ci,
  `details` json DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `title` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `interview_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'free',
  `question_limit` int DEFAULT '0',
  `time_limit` int DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_interview_history_id` (`id`),
  CONSTRAINT `interview_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `interview_history`
--

LOCK TABLES `interview_history` WRITE;
/*!40000 ALTER TABLE `interview_history` DISABLE KEYS */;
INSERT INTO `interview_history` VALUES (1,1,'',7.5,'Ứng viên có kinh nghiệm với các framework frontend phổ biến nhưng cần cải thiện kỹ năng giải thích và đưa ra ví dụ cụ thể.','[{\"question\": \"Bạn có kinh nghiệm với framework nào không? (VD: React, Vue, Angular)\", \"evaluation\": \"Câu trả lời ngắn gọn nhưng chưa cụ thể về mức độ kinh nghiệm và dự án thực tế.\", \"ideal_answer\": \"Tôi có hơn 2 năm kinh nghiệm làm việc với React, trong đó tôi đã phát triển một số ứng dụng web phức tạp. Ngoài ra, tôi cũng đã thử nghiệm với Vue trong một dự án nhỏ.\", \"candidate_answer\": \"Tôi đã làm việc với React và một chút với Vue.\"}]','2026-02-24 11:44:36',NULL,'free',6,120),(6,1,'Tự do',8,'Ứng viên có kinh nghiệm thực tế với các framework phổ biến, điều này cho thấy họ có khả năng làm việc trong môi trường phát triển hiện đại.','[{\"question\": \"Bạn có kinh nghiệm với framework nào không? (VD: React, Vue, Angular)\", \"evaluation\": \"Ứng viên đã có kinh nghiệm với React, một framework rất phổ biến trong phát triển web, và cũng có một chút kinh nghiệm với Vue. Điều này cho thấy họ có nền tảng vững chắc và khả năng học hỏi các công nghệ mới.\", \"ideal_answer\": \"Tôi đã làm việc với React trong các dự án lớn và cũng có kinh nghiệm với Vue trong một số dự án nhỏ.\", \"candidate_answer\": \"Tôi đã làm việc với React và một chút với Vue.\"}]','2026-02-26 16:47:09','Phỏng vấn Frontend','free',6,120),(7,2,'',8,'Ứng viên có hiểu biết tốt về quy trình phân tích yêu cầu, tuy nhiên cần thêm chi tiết về quy trình cụ thể mà họ sử dụng.','[{\"question\": \"Bạn có thể giải thích quy trình phân tích yêu cầu trong một dự án phần mềm không?\", \"evaluation\": \"Câu trả lời của ứng viên thể hiện sự hiểu biết về việc phân tích yêu cầu, nhưng chưa đủ chi tiết về các bước cụ thể trong quy trình.\", \"ideal_answer\": \"Quy trình phân tích yêu cầu bao gồm các bước như thu thập thông tin từ các bên liên quan, phân loại và ưu tiên các yêu cầu, xác định các mâu thuẫn và thiếu sót, và cuối cùng là làm rõ các yêu cầu chưa rõ ràng thông qua các cuộc họp hoặc phỏng vấn.\", \"candidate_answer\": \"Xem xét, phân tích kỹ các yêu cầu đã thu thập để phát hiện các mâu thuẫn, thiếu sót và làm rõ các yêu cầu chưa rõ ràng.\"}, {\"question\": \"Bạn hãy mô tả quy trình bạn sử dụng để phân tích và làm rõ các yêu cầu trong dự án.\", \"evaluation\": \"Ứng viên chưa cung cấp câu trả lời cho câu hỏi này, điều này có thể cho thấy thiếu sót trong việc mô tả quy trình cụ thể mà họ sử dụng.\", \"ideal_answer\": \"Tôi thường bắt đầu bằng việc thu thập yêu cầu từ các bên liên quan, sau đó phân tích và phân loại chúng theo mức độ ưu tiên. Tiếp theo, tôi tổ chức các cuộc họp để làm rõ các yêu cầu chưa rõ ràng và ghi nhận phản hồi để điều chỉnh yêu cầu cho phù hợp.\", \"candidate_answer\": \"Ứng viên chưa trả lời\"}]','2026-02-27 14:25:58','Phỏng vấn ','free',0,0),(8,1,'Frontend',7.5,'Ứng viên có kinh nghiệm thực tế trong việc sử dụng SQL để phân tích dữ liệu và cung cấp insight cho Ban Giám Đốc. Tuy nhiên, ứng viên chưa thể mô tả một truy vấn SQL cụ thể, điều này có thể ảnh hưởng đến khả năng đánh giá kỹ năng kỹ thuật của họ.','[{\"question\": \"Bạn hãy mô tả một tình huống cụ thể khi bạn đã sử dụng SQL để giải quyết một vấn đề phức tạp trong phân tích dữ liệu?\", \"evaluation\": \"Ứng viên đã mô tả rõ ràng tình huống sử dụng SQL và kết quả đạt được, cho thấy khả năng phân tích và ứng dụng dữ liệu trong công việc.\", \"ideal_answer\": \"Tôi đã sử dụng SQL để kết hợp dữ liệu từ các bảng khách hàng, giao dịch và chi phí marketing. Truy vấn của tôi đã xác định mối quan hệ giữa chi phí và doanh thu, giúp tôi tạo ra dashboard trên Power BI để đưa ra khuyến nghị cho Ban Giám Đốc.\", \"candidate_answer\": \"Khi phân tích hiệu quả của các chiến dịch tiếp thị, tôi đã sử dụng SQL để kết hợp dữ liệu từ nhiều bảng khác nhau, bao gồm dữ liệu khách hàng, dữ liệu giao dịch và dữ liệu chi phí marketing. Tôi đã xây dựng một truy vấn phức tạp để xác định mối quan hệ giữa chi phí tiếp thị với doanh thu, từ đó tạo ra dashboard trực quan trên Power BI để đưa ra khuyến nghị cho Ban Giám Đốc.\"}, {\"question\": \"Bạn có thể mô tả một truy vấn SQL phức tạp mà bạn đã sử dụng để phân tích dữ liệu từ nhiều bảng không?\", \"evaluation\": \"Ứng viên không thể trả lời câu hỏi này, điều này cho thấy họ có thể thiếu kinh nghiệm hoặc không tự tin trong việc mô tả các truy vấn SQL phức tạp.\", \"ideal_answer\": \"Tôi đã thực hiện một truy vấn JOIN giữa các bảng khách hàng và giao dịch để phân tích hành vi mua sắm. Kết quả cho thấy nhóm khách hàng nào có tỷ lệ chuyển đổi cao nhất.\", \"candidate_answer\": \"toi khong biet\"}, {\"question\": \"Bạn có thể mô tả một truy vấn SQL phức tạp mà bạn đã thực hiện và kết quả bạn đạt được từ nó không?\", \"evaluation\": \"Ứng viên đã nêu rõ kết quả từ việc sử dụng SQL, nhưng không cung cấp chi tiết về truy vấn cụ thể, điều này làm giảm khả năng đánh giá kỹ năng kỹ thuật của họ.\", \"ideal_answer\": \"Tôi đã thực hiện một truy vấn phức tạp để phân tích doanh thu theo từng khu vực. Kết quả cho thấy khu vực nào cần tăng cường tiếp thị.\", \"candidate_answer\": \"Thông qua việc phân tích dữ liệu và cung cấp insight từ truy vấn SQL, tôi đã giúp Ban Giám Đốc đưa ra các quyết định chiến lược như điều chỉnh chiến lược giá và tối ưu hóa các chương trình khuyến mãi.\"}]','2026-02-27 15:37:01','Phỏng vấn Frontend','free',8,120),(9,1,'Quản lý dự án',7.5,'Ứng viên có kiến thức về quản lý dự án và rủi ro, nhưng cần cải thiện khả năng trình bày các bước cụ thể hơn.','[{\"question\": \"Bạn có thể mô tả các bước để xác định mục tiêu và phạm vi của một dự án không?\", \"evaluation\": \"Ứng viên chưa cung cấp câu trả lời cho câu hỏi này, điều này có thể ảnh hưởng đến khả năng hiểu biết về quản lý dự án.\", \"ideal_answer\": \"Xác định mục tiêu dự án, phân tích yêu cầu, xác định phạm vi, và tạo tài liệu phạm vi.\", \"candidate_answer\": \"Ứng viên chưa trả lời\"}, {\"question\": \"Bạn có thể giải thích về cách bạn quản lý rủi ro trong một dự án không?\", \"evaluation\": \"Ứng viên đã cung cấp một câu trả lời chi tiết về cách quản lý rủi ro, cho thấy khả năng phân tích và lập kế hoạch tốt.\", \"ideal_answer\": \"Liệt kê rủi ro, phân tích tác động, lập kế hoạch ứng phó và theo dõi rủi ro trong suốt dự án.\", \"candidate_answer\": \"Xác định những gì sẽ được bao gồm và loại trừ trong dự án, và tạo tài liệu phạm vi để đảm bảo tất cả các bên liên quan đều có cùng hiểu biết. Bắt đầu bằng việc liệt kê tất cả các rủi ro có thể xảy ra trong dự án dựa trên thông tin hiện có và kinh nghiệm từ các dự án trước.\"}]','2026-02-27 18:33:45','Phỏng vấn Quản lý dự án','free',5,120),(10,1,'Frontend Lowcode Dev',8,'Ứng viên có kinh nghiệm thực tế trong việc phát triển ứng dụng web bằng OutSystems và đã áp dụng các thực hành phát triển low-code. Tuy nhiên, câu trả lời cần cụ thể hơn về quy trình hợp tác với các nhóm chức năng.','[{\"question\": \"Bạn có thể mô tả quy trình hợp tác với các nhóm chức năng khác như BA, Backend và QA trong dự án trước đây không?\", \"evaluation\": \"Câu trả lời không trực tiếp trả lời về quy trình hợp tác với các nhóm chức năng như BA, Backend và QA. Ứng viên cần cung cấp thông tin cụ thể hơn về cách thức làm việc và tương tác với các nhóm này.\", \"ideal_answer\": \"Trong dự án trước, tôi thường xuyên họp với nhóm BA để hiểu rõ yêu cầu và mục tiêu của dự án. Sau đó, tôi phối hợp với nhóm Backend để đảm bảo rằng các API được phát triển đúng theo yêu cầu. Cuối cùng, tôi làm việc với nhóm QA để kiểm tra và đảm bảo chất lượng ứng dụng trước khi triển khai.\", \"candidate_answer\": \"Trong dự án trước đây, tôi đã tham gia phát triển ứng dụng web bằng OutSystems, nơi tôi chịu trách nhiệm xây dựng các giải pháp low-code nhằm hỗ trợ quá trình chuyển đổi số của doanh nghiệp. Tôi đã áp dụng các thực hành phát triển low-code hiện đại để đảm bảo ứng dụng có thể đáp ứng nhanh chóng và hiệu quả các yêu cầu kinh doanh.\"}]','2026-03-02 21:06:00','Phỏng vấn Frontend Lowcode Dev','free',5,120),(11,5,'Tự do',5,'Ứng viên thể hiện sự quan tâm đến vị trí nhưng thiếu thông tin chi tiết về kinh nghiệm và quy trình làm việc.','[{\"question\": \"Bạn có thể cho tôi biết về kinh nghiệm của bạn với công nghệ mà bạn đã sử dụng gần đây nhất trong dự án?\", \"evaluation\": \"Ứng viên chưa cung cấp thông tin về kinh nghiệm công nghệ.\", \"ideal_answer\": \"Tôi đã sử dụng công nghệ X trong dự án Y, và tôi đã thực hiện Z để đạt được kết quả A.\", \"candidate_answer\": \"Ứng viên chưa trả lời\"}, {\"question\": \"Bạn có thể giải thích quy trình thu thập yêu cầu dự án mà bạn đã thực hiện trong quá khứ không?\", \"evaluation\": \"Ứng viên không cung cấp thông tin về quy trình thu thập yêu cầu.\", \"ideal_answer\": \"Quy trình thu thập yêu cầu bao gồm việc xác định bên liên quan, tổ chức các cuộc họp để thu thập thông tin và tài liệu yêu cầu.\", \"candidate_answer\": \"Ứng viên chưa trả lời\"}]','2026-03-11 16:18:56','Phỏng vấn Tự do','free',5,120),(12,6,'Tự do',0,'Ứng viên chưa cung cấp thông tin về quy trình phát triển phần mềm.','[{\"question\": \"Bạn có thể cho tôi biết bạn hiểu gì về quy trình phát triển phần mềm?\", \"evaluation\": \"Ứng viên chưa đưa ra câu trả lời cho câu hỏi này.\", \"ideal_answer\": \"Quy trình phát triển phần mềm là một chu trình bao gồm các bước như phân tích yêu cầu, thiết kế, lập trình, kiểm thử và bảo trì để tạo ra phần mềm chất lượng.\", \"candidate_answer\": \"Ứng viên chưa trả lời\"}]','2026-03-14 20:04:57','Phỏng vấn Tự do','timed',5,120);
/*!40000 ALTER TABLE `interview_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `jd_templates`
--

DROP TABLE IF EXISTS `jd_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `jd_templates` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_jd_templates_title` (`title`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `jd_templates`
--

LOCK TABLES `jd_templates` WRITE;
/*!40000 ALTER TABLE `jd_templates` DISABLE KEYS */;
INSERT INTO `jd_templates` VALUES (1,'Frontend Developer (ReactJS / Next.js)','Mô tả công việc:\n\nTham gia phát triển các tính năng giao diện cho nền tảng Web App (SaaS) của công ty sử dụng ReactJS và Next.js.\n\nTối ưu hóa hiệu suất ứng dụng (Web Performance, SEO) và đảm bảo trải nghiệm người dùng (UX/UI) mượt mà trên đa thiết bị.\n\nPhối hợp chặt chẽ với đội ngũ Backend (API) và Design (Figma) để triển khai tính năng.\n\nYêu cầu ứng viên:\n\nTối thiểu 1 năm kinh nghiệm làm việc thực tế với ReactJS.\n\nNắm vững HTML5, CSS3, JavaScript (ES6+).\n\nCó kinh nghiệm quản lý State (Redux, Zustand hoặc Context API).\n\nHiểu biết về RESTful API, Git.\n\nCó tư duy giải quyết vấn đề tốt, biết cách debug và xử lý lỗi hiển thị.','2026-02-27 11:12:51'),(2,'Chuyên viên Digital Marketing (Performance)','Mô tả công việc:\n\nLên kế hoạch, thực thi và tối ưu hóa các chiến dịch quảng cáo trả phí trên đa nền tảng (Facebook Ads, Google Ads, TikTok Ads).\n\nTheo dõi, phân tích các chỉ số hiệu quả (CPA, ROAS, CTR) và lập báo cáo định kỳ.\n\nPhối hợp với team Content/Design để tối ưu hóa nội dung và hình ảnh quảng cáo (A/B Testing).\n\nCập nhật liên tục các xu hướng và thuật toán mới của các nền tảng mạng xã hội.\n\nYêu cầu ứng viên:\n\nCó ít nhất 1.5 năm kinh nghiệm chạy Ads thực chiến với ngân sách trên 50 triệu/tháng.\n\nTư duy nhạy bén với các con số, sử dụng thành thạo Google Analytics, Excel.\n\nKỹ năng giải quyết vấn đề nhanh chóng khi tài khoản quảng cáo gặp sự cố.','2026-02-27 11:13:30'),(3,'Nhân viên Kinh doanh Doanh nghiệp (B2B Sales)','Mô tả công việc:\n\nTìm kiếm, tiếp cận và xây dựng mối quan hệ với các khách hàng là doanh nghiệp (B2B) có nhu cầu sử dụng phần mềm công nghệ của công ty.\n\nGặp gỡ, tư vấn giải pháp, tiến hành demo sản phẩm và thuyết phục khách hàng ký kết hợp đồng.\n\nTheo dõi quá trình triển khai hợp đồng và chăm sóc khách hàng sau bán (After-sales) để duy trì tỷ lệ tái ký.\n\nYêu cầu ứng viên:\n\nTừng có kinh nghiệm làm Sales B2B (ưu tiên mảng phần mềm, dịch vụ IT).\n\nKỹ năng giao tiếp, thuyết trình và đàm phán xuất sắc.\n\nKhông ngại bị từ chối, có khả năng chịu áp lực doanh số cao.\n\nTác phong chuyên nghiệp, ngoại hình sáng là một lợi thế.','2026-02-27 11:13:43'),(4,'Chuyên viên Tuyển dụng Nhân sự (Talent Acquisition)','Mô tả công việc:\n\nTiếp nhận yêu cầu tuyển dụng từ các phòng ban, lập kế hoạch và triển khai tìm kiếm ứng viên (đặc biệt là các vị trí IT và Marketing).\n\nLọc CV, phỏng vấn sơ vấn (Phone screening) và tổ chức các buổi phỏng vấn trực tiếp.\n\nMở rộng mạng lưới ứng viên qua các kênh LinkedIn, Facebook Groups, các sự kiện Job Fair.\n\nĐàm phán lương (Offer), làm thủ tục tiếp nhận nhân sự mới (Onboarding).\n\nYêu cầu ứng viên:\n\nCó 2 năm kinh nghiệm làm tuyển dụng, từng tuyển dụng các vị trí công nghệ là điểm cộng lớn.\n\nKỹ năng đánh giá con người, giao tiếp khéo léo và thấu hiểu tâm lý ứng viên.\n\nCó khả năng xây dựng thương hiệu tuyển dụng (Employer Branding).','2026-02-27 11:14:04'),(5,'Chuyên viên Phân tích Dữ liệu (Data Analyst)','Mô tả công việc:\n\nThu thập, làm sạch và xử lý dữ liệu từ nhiều nguồn khác nhau của hệ thống.\n\nXây dựng các Dashboard/Báo cáo tự động (Power BI, Tableau) để theo dõi hành vi người dùng và hiệu quả kinh doanh.\n\nCung cấp insight (góc nhìn sâu) từ dữ liệu để tư vấn cho Ban Giám Đốc đưa ra các quyết định chiến lược.\n\nYêu cầu ứng viên:\n\nThành thạo SQL (truy vấn dữ liệu phức tạp) và Python (Pandas, Numpy).\n\nCó kinh nghiệm sử dụng ít nhất một công cụ BI (PowerBI, Tableau, Looker).\n\nCó tư duy phân tích nhạy bén (Analytical thinking) và kỹ năng kể chuyện bằng dữ liệu (Data Storytelling).','2026-02-27 11:14:31');
/*!40000 ALTER TABLE `jd_templates` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `support_messages`
--

DROP TABLE IF EXISTS `support_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `support_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `admin_id` int DEFAULT NULL,
  `message` text COLLATE utf8mb4_unicode_ci,
  `sender_type` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_read` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_support_messages_user_id` (`user_id`),
  KEY `ix_support_messages_id` (`id`),
  CONSTRAINT `support_messages_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `support_messages`
--

LOCK TABLES `support_messages` WRITE;
/*!40000 ALTER TABLE `support_messages` DISABLE KEYS */;
INSERT INTO `support_messages` VALUES (1,1,NULL,'hi','user',1,'2026-03-04 19:26:41'),(2,1,1,'hello','admin',1,'2026-03-04 19:52:34'),(3,1,NULL,'toi can tro giup','user',1,'2026-03-04 19:52:46'),(4,5,NULL,'hi','user',1,'2026-03-16 19:17:21'),(5,5,NULL,'Admin hiện không online. Chúng tôi sẽ phản hồi sớm nhất khi có mặt! 🙏','system',1,'2026-03-16 19:17:21'),(6,5,1,'hi','admin',1,'2026-03-17 20:34:28'),(7,5,1,'bạn cần giúp gì','admin',1,'2026-03-17 20:34:37');
/*!40000 ALTER TABLE `support_messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `system_config`
--

DROP TABLE IF EXISTS `system_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_config` (
  `id` int NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `setting_value` text COLLATE utf8mb4_unicode_ci,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_system_config_setting_key` (`setting_key`),
  KEY `ix_system_config_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `system_config`
--

LOCK TABLES `system_config` WRITE;
/*!40000 ALTER TABLE `system_config` DISABLE KEYS */;
INSERT INTO `system_config` VALUES (1,'system_prompt','Bạn là một Giám đốc Nhân sự (HR) chuyên nghiệp đang phỏng vấn ứng viên:\nQuy tắc bắt buộc:\n1. Dựa sát vào mô tả công việc (JD) để đặt câu hỏi chuyên môn phù hợp với ĐÚNG NGÀNH NGHỀ đó.\n2. Trả lời cực kỳ ngắn gọn, súc tích (<50 từ).\n3. Mỗi lần chỉ đặt MỘT câu hỏi. Độ khó tăng dần theo thời gian.\n4. Tự hiểu và bỏ qua các lỗi phát âm sai/chính tả do nhận diện giọng nói.\n5. KHÔNG BAO GIỜ được dùng các văn mẫu như \"Xin lỗi, hãy tập trung vào chuyên môn...\". Nếu ứng viên lảng tránh, hãy tự động chuyển sang câu hỏi chuyên môn khác một cách tự nhiên.\n6. NẾU ỨNG VIÊN CHỦ ĐỘNG CHỌN VỊ TRÍ (VD: \"Tôi muốn phỏng vấn BA\", \"Hỏi tôi về React đi\"): Hãy vui vẻ đồng ý ngay lập tức (VD: \"Vâng, chúng ta bắt đầu nhé.\") và ĐẶT NGAY câu hỏi chuyên môn đầu tiên về lĩnh vực đó. Tuyệt đối không từ chối hay xin lỗi.\n\nQUY TẮC CHUYỂN CÂU HỎI QUAN TRỌNG:\n    Nếu ứng viên trả lời bằng các cụm từ như: \"Tôi không biết\", \"Bỏ qua\", \"Next\", \"Chưa tìm hiểu kỹ\", hoặc có ý định từ bỏ câu hỏi hiện tại:\n    1. KHÔNG được mắng mỏ, KHÔNG được gợi ý thêm, và TUYỆT ĐỐI KHÔNG giải thích đáp án cho họ.\n    2. Hãy ghi nhận sự chân thật của họ một cách ngắn gọn (Ví dụ: \"Không sao, chúng ta sẽ chuyển sang vấn đề khác\").\n    3. LẬP TỨC đặt ra một CÂU HỎI MỚI hoàn toàn khác để tiếp tục luồng phỏng vấn.\n    4. Khi tổng hợp báo cáo sau này, hãy tự động chấm câu hỏi bị bỏ qua đó là 0 điểm.\n\nKỊCH BẢN XỬ LÝ CÁC TÌNH HUỐNG ĐẶC BIỆT TỪ ỨNG VIÊN:\n1. KHI ỨNG VIÊN HỎI NGƯỢC LẠI (VD: \"Anh/chị nghĩ sao?\", \"Công ty mình đang dùng công nghệ gì?\"): \n   - TUYỆT ĐỐI KHÔNG trả lời câu hỏi của họ. \n   - Hãy từ chối khéo léo: \"Rất tiếc, trong khuôn khổ buổi phỏng vấn này, tôi đang đóng vai trò tìm hiểu về bạn. Chúng ta sẽ dành phần hỏi đáp về công ty vào cuối buổi nhé. Bây giờ, mời bạn tiếp tục với câu hỏi...\"\n2. KHI ỨNG VIÊN XIN LỜI KHUYÊN/GỢI Ý (VD: \"Em nên trả lời sao?\", \"Gợi ý cho em với\"): \n   - TUYỆT ĐỐI KHÔNG đưa ra đáp án hay gợi ý chuyên môn. \n   - Hãy đáp lời: \"Tôi muốn lắng nghe tư duy độc lập của bạn. Bạn cứ thoải mái chia sẻ theo cách hiểu của mình nhé, đúng sai không quan trọng bằng cách bạn tiếp cận vấn đề.\"\n3. PHÂN BIỆT \"TRẢ LỜI SAI\" VÀ \"BỎ QUA\": \n   - Chỉ được coi là \"Bỏ qua\" khi ứng viên dùng rõ các từ \"Next, bỏ qua, tôi không biết, chịu\". \n   - Nếu ứng viên có cố gắng đưa ra một vài ý kiến (dù sai, ngô nghê, hoặc ấp úng), HÃY GHI NHẬN ĐÓ LÀ MỘT CÂU TRẢ LỜI, phản hồi ngắn gọn (VD: \"Cảm ơn góc nhìn của bạn\") và chuyển sang câu hỏi tiếp theo.','2026-02-27 20:00:52'),(2,'temperature','0.7',NULL);
/*!40000 ALTER TABLE `system_config` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `transaction_history`
--

DROP TABLE IF EXISTS `transaction_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `transaction_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `amount` int DEFAULT NULL,
  `transaction_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `note` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_transaction_history_id` (`id`),
  CONSTRAINT `transaction_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `transaction_history`
--

LOCK TABLES `transaction_history` WRITE;
/*!40000 ALTER TABLE `transaction_history` DISABLE KEYS */;
INSERT INTO `transaction_history` VALUES (1,2,100,'add_credits','Admin admin@gmail.com cộng thêm 100 credits.','2026-02-27 15:21:50'),(2,3,100,'add_credits','Admin admin@gmail.com cộng thêm 100 credits.','2026-03-02 21:16:31'),(3,5,10000,'upgrade_pro','Nâng cấp gói Pro (Instant) cho thanhhoangk25@gmail.com','2026-03-11 17:56:34');
/*!40000 ALTER TABLE `transaction_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `transactions`
--

DROP TABLE IF EXISTS `transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `amount` int DEFAULT NULL,
  `txn_ref` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_transactions_txn_ref` (`txn_ref`),
  KEY `ix_transactions_user_id` (`user_id`),
  KEY `ix_transactions_id` (`id`),
  CONSTRAINT `transactions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `transactions`
--

LOCK TABLES `transactions` WRITE;
/*!40000 ALTER TABLE `transactions` DISABLE KEYS */;
/*!40000 ALTER TABLE `transactions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_profiles`
--

DROP TABLE IF EXISTS `user_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_profiles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `address` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `website` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `github` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `linkedin` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `summary` text COLLATE utf8mb4_unicode_ci,
  `skills` text COLLATE utf8mb4_unicode_ci,
  `avatar` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `ix_user_profiles_id` (`id`),
  KEY `ix_user_profiles_user_id` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_profiles`
--

LOCK TABLES `user_profiles` WRITE;
/*!40000 ALTER TABLE `user_profiles` DISABLE KEYS */;
INSERT INTO `user_profiles` VALUES (1,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(2,2,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(3,3,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(4,4,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),(5,5,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'data:image/jpeg;base64,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'),(6,6,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
/*!40000 ALTER TABLE `user_profiles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `full_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hashed_password` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `credits` int DEFAULT '10',
  `last_token_reset_date` date DEFAULT NULL,
  `plan` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'free',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_email` (`email`),
  KEY `ix_users_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'admin@gmail.com','Admin','$argon2id$v=19$m=65536,t=3,p=4$3huDkNL6/z/nnNM6J2QMIQ$CZNrPmFBGbkeiPm32ahZz8GmmmT+3y6ohZG402glZkE','admin',10000,'2026-05-12','pro'),(2,'test@gmail.com','Hoang Thanh','$argon2id$v=19$m=65536,t=3,p=4$c855zxmj1Pr/vxfiXEupFQ$GSULh1MR3rWp8jjLC1x1qVVcrYepR5PsD2x87erO0EI','user',110,NULL,'free'),(3,'test1@gmail.com','Ta Thanh','$argon2id$v=19$m=65536,t=3,p=4$kXJOKcWYMybE+B9jrHVO6Q$DUVi/AGdiQY8py0WwELmbVdDNXdsjf21QiMbWdgwaXM','user',110,NULL,'free'),(4,'thanhheo7749@gmail.com','2051_ Tạ Hoàng Thành','$argon2id$v=19$m=65536,t=3,p=4$4FwrhdB6D0GoldI6pxTifA$9YN1z1aSI8YK8TR5j4+2QQQq81Ob0ehs4S7TioQHi0I','user',50,'2026-03-07','free'),(5,'thanhhoangk25@gmail.com','Hoàng Thành','$argon2id$v=19$m=65536,t=3,p=4$LeV8z7k3xhijVIpRSknp3Q$5C227fB6rxSMNc5YDyOsEdU+1FAkN83jMBHZ4FlWBIs','user',10000,'2026-03-16','pro'),(6,'testuser@example.com','Test User','$argon2id$v=19$m=65536,t=3,p=4$KUVorXVOybl3rnWOcS6ltA$5SXybDpZy9g9d0tKn5JiXYSmVpCKHJxR6oKqDoZo8vc','user',100,'2026-03-14','free');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'speakcv'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-12 11:06:37
