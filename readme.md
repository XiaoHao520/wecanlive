WE CAN LIVE 直播平台
====================


一、关于系统选项的说明列表
--------------------------

| 显示标题              | 选项名                          | 类型     |   备注                             |
|-----------------------|---------------------------------|----------|------------------------------------|
| 文章-会员服务条款     | article_member_license          | 富文本   |                                    |
| 文章-举报规则         | article_inform_rules            | 富文本   |                                    |
| 文章-VIP规则          | article_vip_rules               | 富文本   |                                    |
| 等级规则              | level_rules                     | JSON     | 五种等级的升级级差关系             |
| 家族等级规则          | family_level_rules              | JSON     | 家族升级所需贡献值
| VIP规则               | vip_rules                       | JSON     | 后台VIP管理的VIP权限矩阵以及LOGO   |
| 机器人规则            | robot_rules                     | JSON     |                                    |
| 签到星星奖励          | daily_sign_award_stars          | JSON     | [1,2,3,4]为连续签到奖励的星星数量  |
| 星光任务点数-观看     | star_mission_points_watch       | 整数     | 每观看30分钟直播获得的星星数量     |
| 星光任务点数-分享     | star_mission_points_share       | 整数     | 每分享一个直播间获得的星星数量     |
| 星光任务点数-邀请     | star_mission_points_invite      | 整数     | 每邀请一个好友加入获得的星星数量   |
| 星光任务点数-完善信息 | star_mission_points_information | 整数     | 完善个人信息获得的星星数量         |
| 发布一条弹幕需要金币  | coins_barrage_cost              | 整数     |                                    |
| 跑马灯设置            | marque_settings                 | JSON     | 等级区间、VIP级别、消费要求        |
| 经验值-登录签到       | experience_points_login         | 整数     | 每次签到获得的经验值               |
| 经验值-公开分享       | experience_points_share         | 整数     | 每次公开分享获得的经验值           |
| 经验值-收到礼物       | experience_points_prize_receive | 整数     | 每次收到礼物获得的经验值           |
| 经验值-送出礼物       | experience_points_prize_send    | 整数     | 每次送出礼物获得的经验值           |
| 经验值-观看直播       | experience_points_watch         | 整数     | 每次观看直播获得的经验值           |
| 经验值-本人直播       | experience_points_live          | 整数     | 每次本人直播获得的经验值           |
| 金币钻石汇率          | exchange_diamonds_per_coin      | 整数     | 一个金币可兑换的钻石数            |
| 金币充值规则          | coin_recharge_rules             | JSON     | 金币充值规则                     |
| 客户服务中心链接      | url_customer_center             | 文本      |                                |
| 元气宝盒金币最大值     | max_star_box_coin               | 整数     | 打开元气宝盒如果是金币的最大值     |
| 元气宝盒金币最小值     | min_star_box_coin               | 整数     | 打开元气宝盒如果是金币的最小值     |
| 元气宝盒钻石最大值     | max_star_box_diamond            | 整数     | 打开元气宝盒如果是钻石的最大值     |
| 元气宝盒钻石最小值     | min_star_box_diamond            | 整数     | 打开元气宝盒如果是钻石的最小值     |
| 元气宝盒随机礼物列表   | star_box_prize_list             | JSON     | 打开元气宝盒随机礼物列表和数量     |
| VIP Logo設置          | vip_logo                        | JSON     | [1,2,3]等爲圖片id
| VIP 進場特效          | vip_special_effects             | JSON     | [1,2]爲圖片id VIP進入時播放的特效
| VIP 回饋禮包設定       | vip_rebate                      | JSON     | VIP 回饋禮包
| 家族修改头衔消耗金币   | family_modify_title_coin        | 整数     | 家族长修改头衔每次消耗金币         |
| 家族任务元件          | family_mission_element          | JSON     | 家族任务元件 数值为0是禁用         |
| 家族任务奖励元件      |  family_award_element            | JSON     | 家族任务奖励元件                 |
| 引导页图片            |  guide_page                     | JSON     | 引导页图片                       |
| 邀请好友金币奖励       | invite_award                    | 整数     | 奖励金币个数
| 熱門搜索標籤           | search_hot_key                  | 文本     | 熱門搜索標籤