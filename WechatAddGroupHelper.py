# -*- coding: utf-8 -*- 
"""
Project: HelloWorldPython
Creator: DoubleThunder
Create time: 2019-07-02 20:43
微信加群助手，实现多个功能：
1、通过关键字自动同意加好友。
2、通过关键字自动邀请好友入群。
    再添加多个群。
3、微信断线后发送提醒邮件。
4、腾讯 AI 自动回复。

需要安装的库有：
itchat
apscheduler
yagmail
requests
"""
import time
import string
import random
import re
import hashlib
from urllib import parse
from datetime import datetime
from collections import OrderedDict
import platform

import itchat
from itchat.content import (
    NOTE,
    TEXT,
    FRIENDS
)
from apscheduler.schedulers.blocking import BlockingScheduler
import requests
import yagmail

# start ----------------------------------- 邮件提醒功能 ----------------------------------- start
IS_OPEN_EMAIL_NOTICE = True
email_user = '发件人的邮箱'  # 发件人的邮箱
email_password = '授权码'  # 邮箱授权码（并非邮箱密码）
email_host = 'smtp.qq.com'  # 对应邮箱的 host，这个是 qq 的。
to_emails = ['xx@qq.com', 'xx@gmail.com']  # 填写你需要发送提醒的邮件，可填写多个用『，』号分隔

if IS_OPEN_EMAIL_NOTICE:
    yag = yagmail.SMTP(user=email_user, password=email_password, host=email_host)
#   end ----------------------------------- 邮件提醒功能 ----------------------------------- end


# start ----------------------------------- 自动回复属性 ----------------------------------- start
# appid , appkey 申请地址：https://ai.qq.com/product/nlpchat.shtml
IS_OPEN_AUTO_REPLY = True
NLPCHAT_APP_ID = '你的appid'
NLPCHAT_APP_KEY = '你的appkey'
NLPCHAT_URL = 'https://api.ai.qq.com/fcgi-bin/nlp/nlp_textchat'
MSG_SUFFIX = " ——来自小鲲的 auto reply"  # 自动回复的后缀(可为空)
#   end ----------------------------------- 自动回复属性 ----------------------------------- end


# start ----------------------------------- 群名称与关键词设置 ----------------------------------- start

IS_OPEN_ADD_GROUP = True
# 群聊名称，可设置多个。注意顺序（前面的群人数已满(500)，才会邀请后面的群） 注意：必须要把需要的群聊保存到通讯录
group_name_list = ['EverydayWechat 交流1群', 'EverydayWechat 交流2群']
add_group_keys = '加群，拉群，进群'  # 加群关键词，多个词用「，」分隔
IS_ENTER_MULT_GROUP = True  # 是否可以加入多个群组，如果为 True，用户重复发送『加群』，则会依次邀请加入下一个群组

IS_AUTO_ADD_FRIEND = True
add_friend_keys = 'github，加群，大佬，女装，大神，交流，python'  # 通过好友关键词，多个词用「，」分隔
#   end ----------------------------------- 群名称与关键词设置 ----------------------------------- end

# start ----------------------------------- 提醒设置 ----------------------------------- start

note_first_meet_text = '我是智障时长两年半的个人沙雕机器人小鲲，喜欢复制、粘贴、BUG、掉头发。发送关键词：『加群』则会自动邀请你入群！ '  # 加群成功后的第一句话
note_add_repeat_answer = '请不要重复加群！'
note_auto_reply_text = '我是智障时长两年半的个人沙雕机器人小鲲，请到群里再聊。'  # 默认的自动回复
# 新用户入群发送的公告
note_invite_welcome = '''@{atname}\u2005欢迎加入群，请查看群规...

此群禁止发广告。
无法登录网页微信的问题，无有效解决办法。

《群里提问的艺术》
怎样提问：
1. 别问毫无意义的问题：『群里又xxx大佬吗？、在吗？、有没有人会？』
2. 用词准确，问题明确。
3. 描述清晰，信息充足：准确有效的信息、做过什么尝试、想要得到什么回答。'''
#   end ----------------------------------- 提醒设置 ----------------------------------- end

# start ----------------------------------- 一些正则表达式 ----------------------------------- start
uidlist_compile = re.compile(r"(?<!'Self': )\<ChatroomMember:.*?'UserName': '(.*?)', 'NickName'.*?")  # 筛选出群所有用户的 uid
friend_content_compile = re.compile(r'content="(.*?)"')  # 判断消息是否为加好友的请求
add_friend_compile = re.compile('|'.join(i.strip() for i in
                                         re.split(r'[,，]+', add_friend_keys) if i), re.I)  # 通过关键词同意加好友请求
add_group_compile = re.compile('|'.join(i.strip() for i in
                                        re.split(r'[,，]+', add_group_keys) if i), re.I)  # 通过关键词同意邀请好友加群
invite_compile = re.compile(r'邀请"(.*?)"加入了群聊\s*$')  # 判断此群通知是否为新成员加群
#   end ----------------------------------- 一些正则表达式 ----------------------------------- end


# start ----------------------------------- 一些其他设置 ----------------------------------- start
group_infos_dict = OrderedDict()  # 群信息字典
wechat_nick_name = ''  # 此微信号的名称
LONG_TEXT = string.ascii_letters + string.digits + string.punctuation  # 长字符，用于获取随机字符
HEART_BEAT_INTERVAL_MINUTES = 15  # 心跳时间间隔


#   end ----------------------------------- 一些其他设置 ----------------------------------- end


def init_info():
    """ 初始化数据 """
    global wechat_nick_name
    global IS_OPEN_EMAIL_NOTICE

    wechat_nick_name = itchat.search_friends()['NickName']  # 获取此微信号的昵称
    set_note('微信号『{}』登录成功！'.format(wechat_nick_name))

    try:
        if IS_OPEN_EMAIL_NOTICE:
            yag.login()
            print('邮件提醒功能已开启。')
        else:
            print('邮件提醒功能已关闭。')
    except Exception as exception:
        # print(str(exception))
        print('邮件配置有错，已关闭邮件提醒功能。')
        IS_OPEN_EMAIL_NOTICE = False

    if IS_AUTO_ADD_FRIEND:
        print('自动同意添加好友已开启，同意关键词：{}。'.format(add_friend_keys))
    else:
        print('自动同意添加好友已关闭。')

    if IS_OPEN_ADD_GROUP:  # 已开启邀请功能

        print('自动邀请群聊功能已开启，加群关键词：{}'.format(add_group_keys))
        itchat.get_chatrooms(update=True)  # 更新群聊数据。
        for group_name in group_name_list:
            group_list = itchat.search_chatrooms(name=group_name)  # 通过群聊名获取群聊信息
            group_info = {}
            if group_list:
                group_uuid = group_list[0]['UserName']
                group = itchat.update_chatroom(group_uuid, detailedMember=True)
                group_uuid = group['UserName']
                group_info['group_name'] = group_name  # 群聊名称
                group_info['group_uuid'] = group_uuid  # 群聊 uuid
                count = len(group['MemberList'])  # 群聊人数
                group_info['count'] = count
                member_uid_list = uidlist_compile.findall(str(group))  # 根据正则取出群组里所有用户的 uuid。
                if member_uid_list:
                    group_info['member_uid_list'] = member_uid_list
                group_infos_dict[group_uuid] = group_info
                print('群聊『{}』已注册，人数为：{}。'.format(group_name, count))

            else:
                note = '没有找到群聊「{}」 注意：必须要把需要的群聊保存到通讯录。'.format(group_name)
                set_note(note)
                break
    else:
        print('自动邀请群聊功能已关闭。')
    print('项目初始化已完成...开始正常工作。')
    print('-' * 50)


def update_group_info(group_uuid):
    """ 用户加群后更新群信息，主要是为了更新群会员信息 """
    group = itchat.update_chatroom(group_uuid, detailedMember=True)
    group_info = group_infos_dict[group_uuid]
    group_info['group_uuid'] = group['UserName']
    group_info['count'] = len(group['MemberList'])
    member_uid_list = uidlist_compile.findall(str(group))  # 根据正则取出群组里所有用户的 uid。
    if member_uid_list:
        group_info['member_uid_list'] = member_uid_list
    group_infos_dict[group_uuid] = group_info
    set_note('已更新群聊『{}』成员的信息。'.format(group['NickName']))


@itchat.msg_register(FRIENDS)
def add_friends_msg(msg):
    """ 监听添加好友请求 为了自动同意好友请求"""

    if not IS_AUTO_ADD_FRIEND:  # 如果是已关闭添加好友功能，则直接返回
        return
        # print(json.dumps(msg, ensure_ascii=False))
    content = msg['RecommendInfo']['Content']  # 获取验证消息
    if add_friend_compile.findall(content):
        time.sleep(random.randint(1, 2))  # 随机休眠（1~3）秒，用于防检测机器人
        itchat.add_friend(**msg['Text'])  # 同意加好友请求
        time.sleep(random.randint(1, 2))
        itchat.send(note_first_meet_text, msg['RecommendInfo']['UserName'])  # 给刚交的朋友发送欢迎语句
        note = '已添加好友：{}'.format(msg['RecommendInfo']['NickName'])
        set_note(note)
    else:
        note = '添加好友失败：用户「{}」 发来的验证消息「{}」。'.format(msg['RecommendInfo']['NickName'], content)
        set_note(note)


@itchat.msg_register([TEXT])
def deal_with_msg(msg):
    """ 监听并处理好友消息 """
    # print(json.dumps(msg, ensure_ascii=False))
    text = msg["Text"]  # 获取好友发送的话
    userid = msg['FromUserName']  # 获取好友的 uid
    nickname = msg['User']['NickName']  # 获取好友的昵称
    is_add_group = add_group_compile.findall(text)  # 检查是否为加群关键词
    if is_add_group and IS_OPEN_ADD_GROUP:
        group_info_list = list(group_infos_dict.values())

        for group_info in group_info_list:
            group_name = group_info['group_name']
            if userid not in group_info['member_uid_list']:  # 用户不在此群中
                if group_info['count'] < 500:  # 群聊人数低于 500
                    time.sleep(random.randint(1, 2))  # 随机休眠 1 到 2 秒
                    # 发送群邀请
                    itchat.add_member_into_chatroom(group_info['group_uuid'], [{'UserName': userid}],
                                                    useInvitation=True)
                    note = '已给『{}』发送加群『{}』邀请通知。'.format(nickname, group_name)
                    set_note(note)
                    break
                else:
                    print('群聊『{}』人数已满。'.format(group_name))

            else:  # 用户在已在此群聊中
                print('『{}』已在群聊『{}』中。'.format(nickname, group_name))
                if not IS_ENTER_MULT_GROUP:  # 如果不让加入多个群, 则退出
                    time.sleep(random.randint(1, 2))
                    # 用户已入群，回复消息：请不要重复加群
                    itchat.send(note_add_repeat_answer, userid)
                    break
        else:
            time.sleep(random.randint(1, 2))
            # 用户已入群，回复消息：请不要重复加群
            itchat.send(note_add_repeat_answer, userid)
    else:
        # 自动回复
        if IS_OPEN_AUTO_REPLY:  # 是否已开启 AI 自动回复
            reply_text = get_nlp_textchat(text, userid)
            reply_text = reply_text if reply_text else ''
            reply_text = reply_text + MSG_SUFFIX
        else:
            reply_text = note_auto_reply_text
        itchat.send(reply_text, userid)
        note = '\n{}发送来的:{}\n自动回复:{}'.format(nickname, text, reply_text)
        set_note(note)


@itchat.msg_register([NOTE], isGroupChat=True)
def group_note_msg(msg):
    """ 群通知处理 """
    # print('NOTE', json.dumps(msg, ensure_ascii=False))
    group_uuid = msg['FromUserName']  # 获取当前群的 uuid
    if group_uuid in group_infos_dict:  # 判断是否为同一个群组
        text = msg['Text']  # 通知的内容
        invite_names = invite_compile.findall(text)  # 判断是否是加入了新用户
        if invite_names:
            invite_name = invite_names[0]  # 加入者的昵称
            time.sleep(random.randint(1, 2))
            if note_invite_welcome:
                # 艾特用户，不过接口已经不支持艾特用户了
                note = note_invite_welcome.format(atname=invite_name)
                itchat.send(note, group_uuid)  # 向群里发送欢迎语句
            update_group_info(group_uuid)  # 更新群信息


def is_online():
    """
    判断微信是否在线
    :return: Bool
    """
    try:
        if itchat.search_friends():
            return True
    except IndexError:
        return False
    return True


def heart_beat():
    """
    定时给文件传输助手发送一段随机字符。用于保持长连接。
    :return:
    """
    if is_online():
        time.sleep(random.randint(1, 100))
        time_ = datetime.now().strftime('%Y-%m-%d %H:%M:%S  ')
        d = ''.join(random.sample(LONG_TEXT, random.randint(10, 20)))
        note = "定时心跳...{}-{}".format(time_, d)
        set_note(note)
    else:
        exit_callback()


def exit_callback():
    """
    微信已经登出
    """
    time_ = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    title = '您服务器上的微信「{}」已离线'.format(wechat_nick_name)
    content = '离线时间：{} \n 离线原因：未知'.format(time_)
    send_mail(title, content)
    set_note(title + content, True)
    stop_scheduler()
    stop_system()


def set_note(note, onle_log=False):
    """
    发送日志
    :param note: 日志内容
    :param onle_log: Bool 是否只输出日志，不发送到文件助手中
    :return:
    """
    if not onle_log:
        itchat.send(note, 'filehelper')
    print(note)  # 简单日志


def send_mail(title, content):
    """
    发送邮件
    :param title: 标题
    :param content: 内容
    """
    if not IS_OPEN_EMAIL_NOTICE:
        return
    try:
        yag.send(to_emails, title, content)
        print('已发送邮件:{}'.format(title))
    except Exception as exception:
        print(str(exception))


def stop_scheduler():
    """ 关闭定时器 """
    if scheduler and scheduler.get_jobs():
        scheduler.shutdown(wait=False)


def stop_system():
    """退出应用"""
    exit(1)


# start ----------------------------------- 自动回复功能 ----------------------------------- start
def get_nlp_textchat(text, userId):
    """
    智能闲聊（腾讯）<https://ai.qq.com/product/nlpchat.shtml>
    接口文档：<https://ai.qq.com/doc/nlpchat.shtml>
    :param text: 请求的话
    :param userId: 用户标识
    """
    try:
        hash_md5 = hashlib.md5(userId.encode("UTF-8"))
        userId = hash_md5.hexdigest().upper()
        # 产生随机字符串
        nonce_str = ''.join(random.sample(LONG_TEXT, random.randint(10, 16)))
        time_stamp = int(time.time())  # 时间戳
        params = {
            'app_id': NLPCHAT_APP_ID,  # 应用标识
            'time_stamp': time_stamp,  # 请求时间戳（秒级）
            'nonce_str': nonce_str,  # 随机字符串
            'session': userId,  # 会话标识
            'question': text  # 用户输入的聊天内容
        }
        # 签名信息
        params['sign'] = getReqSign(params, NLPCHAT_APP_KEY)
        resp = requests.get(NLPCHAT_URL, params=params)
        if resp.status_code == 200:
            content_dict = resp.json()
            if content_dict['ret'] == 0:
                data_dict = content_dict['data']
                return data_dict['answer']
            else:
                print('获取数据失败:{}'.format(content_dict['msg']))
    except Exception as exception:
        print(str(exception))


def getReqSign(parser, app_key):
    '''
    接口鉴权 https://ai.qq.com/doc/auth.shtml
    签名有效期 5 分钟
    1.将 <key, value> 请求参数对按 key 进行字典升序排序，得到有序的参数对列表 N
    2.将列表 N 中的参数对按 URL 键值对的格式拼接成字符串，得到字符串 T（如：key1=value1&key2=value2），
        URL 键值拼接过程 value 部分需要 URL 编码，URL 编码算法用大写字母，例如 %E8，而不是小写 %e8
    3.将应用密钥以 app_key 为键名，组成 URL 键值拼接到字符串 T 末尾，得到字符串 S（如：key1=value1&key2=value2&app_key = 密钥)
    4.对字符串 S 进行 MD5 运算，将得到的 MD5 值所有字符转换成大写，得到接口请求签名
    :param parser:
    :return:
    '''
    params = sorted(parser.items())
    uri_str = parse.urlencode(params, encoding="UTF-8")
    sign_str = '{}&app_key={}'.format(uri_str, app_key)
    # print('sign =', sign_str.strip())
    hash_md5 = hashlib.md5(sign_str.encode("UTF-8"))
    return hash_md5.hexdigest().upper()
#   end ----------------------------------- 自动回复功能 ----------------------------------- end


if __name__ == '__main__':

    if platform.system() in ('Windows', 'Darwin'):
        itchat.auto_login(hotReload=True,
                          loginCallback=init_info, exitCallback=exit_callback)
    else:
        # 命令行显示登录二维码。
        itchat.auto_login(enableCmdQR=2, loginCallback=init_info,
                          exitCallback=exit_callback)
    itchat.run(blockThread=False)

    scheduler = BlockingScheduler()
    scheduler.add_job(heart_beat, 'interval', minutes=HEART_BEAT_INTERVAL_MINUTES)
    scheduler.start()
