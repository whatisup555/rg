from sanic import Sanic, json
from sanic.response import text

from chargingInBupt.auth import authorized, generate_token, authorized_admin, get_username
from chargingInBupt.orm import User, session, ChargeRequest, WaitQueue, Charger, WaitArea
from chargingInBupt.json_validate import json_validate
from chargingInBupt.json_schema import *
from chargingInBupt.config import CONFIG
from sqlalchemy import func


app = Sanic("Charging_in_BUPT")


@app.post('/user/login')
@json_validate(login_json_schema)
async def login(request):
    print(request)
    if request.json:
        username = request.json.get('username')
        password = request.json.get('password')
        user = session.query(User).filter(User.username == username).first()
        if user is None:
            return json({
                "code": -1,
                "message": "Invalid username or password"
            })
        if user.password != password:
            return json({
                "code": -1,
                "message": "Invalid username or password"
            })
        token = generate_token(username, user.admin)
        return json({
            "code": 0,
            "message": "Success",
            "is_admin": user.admin,
            "data": {
                "token": token
            }
        })
    else:
        return json({
            "code": -1,
            "message": "Invalid request"
        })


@app.post('/user/register')
@json_validate(register_json_schema)
async def register(request):
    username = request.json.get('username')
    password = request.json.get('password')
    re_password = request.json.get('re_password')
    if password != re_password:
        return json({
            "code": -1,
            "message": "Password not match"
        })
    user = session.query(User).filter(User.username == username).first()
    if user is not None:
        return json({
            "code": -1,
            "message": "Username already exists"
        })
    user = User(username=username, password=password)
    session.add(user)
    session.commit()
    return json({"code": 0, "message": "Success"})


@app.get('/test')
@authorized()
async def hello_world(request):
    return text("Hello, world.")


@app.get('/test_admin')
@authorized_admin()
async def hello_world(request):
    return text("Hello, admin.")


@app.post('/user/submit_charging_request')
@json_validate(submit_charging_request_json_schema)
@authorized()
async def submit_charging_request(request):
    user = session.query(User).filter(User.username == get_username(request)).first()
    charge_mode = request.json.get('charge_mode')
    require_amount = request.json.get('require_amount')
    battery_size = request.json.get('battery_size')
    # TODO(1): 处理，获取 charge_id
    # 判断是否不在充电状态:没有充电记录或者不存在待充电请求则代表不在充电状态
    record = session.query(ChargeRequest).filter(ChargeRequest.user_id == user.id).first()
    undo_record = session.query(ChargeRequest).filter(ChargeRequest.user_id == user.id and ChargeRequest.state in [1,2,3,4,5]).first()
    charge_time = None
    if record is None or undo_record is None:
        # 请求id
        record_num = session.query(ChargeRequest).count()
        request_id = str(record_num + 1)
        # 插入对应队列
        if session.query(WaitQueue).filter(WaitQueue.statue == 1).count() < CONFIG['cfg']['N']:
            # WaitArea 等候区队列处理
            wait_area = session.query(WaitArea).filter(WaitArea.type == charge_mode).first()
            wait_area.wait_list.append(request_id)
            session.query(WaitArea).filter(WaitArea.type == charge_mode).update({
                "wait_list": wait_area.wait_list
            })

            if charge_mode == "F":
                charge_time = require_amount/CONFIG['cfg']['F_power']*60
            elif charge_mode == "T":
                charge_time = require_amount/CONFIG['cfg']['T_power']*60
            # 生成charge_id,加入队列
            his_front_cars = session.query(WaitQueue).filter(WaitQueue.type == charge_mode).count()
            if his_front_cars == 0:
                charge_id = charge_mode + str(his_front_cars+1)
            else:
                # ？不是很确定这样求最大值对不对
                res = session.query(func.max(int(WaitQueue.charge_id[1:]))).filter(WaitQueue.type == charge_mode).first()
                charge_id = charge_mode + str(res[0]+1)
            session.add(WaitQueue(type=charge_mode, state=1, charge_id=charge_id))
            session.commit()
            # 生成充电请求，插入数据库
            charge_request = ChargeRequest(id=request_id, state=1, user_id=user.id, charge_mode=charge_mode, require_amount=float(require_amount), charge_time=charge_time, battery_size=float(battery_size), charge_id=charge_id)
            session.add(charge_request)
            session.commit()
            success = True
            error_msg = None
            # 如果等待区不为空要调度:似乎只需要调度程序对WaitQueue中state=1的记录不断进行调度即可
        else:
            success = False
            error_msg = "请求失败，等候区已满。"
            charge_id = None
    else:
        success = False
        error_msg = "请求失败，还有待完成充电请求。"
        charge_id = None
    if success:
        return json({
            "code": 0,
            "message": "Success",
            "data": {
                "charge_id": charge_id
            }
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })


@app.post('/user/edit_charging_request')
@json_validate(edit_charging_request_json_schema)
@authorized()
async def edit_charging_request(request):
    user = session.query(User).filter(User.username == get_username(request)).first()
    charge_mode = request.json.get('charge_mode')
    require_amount = request.json.get('require_amount')
    # TODO(1): 处理，修改充电请求
    # 判断是否可以修改
    record = session.query(ChargeRequest).filter(ChargeRequest.user_id == user.id and ChargeRequest.state == 1).first()
    # 存在还在等候区的
    if record is not None:
        # 如果充电模式有修改则放到队列最后
        charge_id = record.charge_id
        if record.charge_mode != charge_mode:
            # WaitArea 等候区相关处理
            wait_area = session.query(WaitArea).filter(WaitArea.type == record.charge_mode).first()
            wait_area.wait_list.remove(record.id)
            wait_area.wait_list.append(record.id)

            res = session.query(func.max(int(WaitQueue.charge_id[1:]))).filter(WaitQueue.type == charge_mode).first()
            charge_id = charge_mode + str(res[0]+1)
            session.query(WaitQueue).filter(WaitQueue.charge_id == record.charge_id).update({
                "charge_id": charge_id
            })
        # 修改后数据写入数据库
        session.query(ChargeRequest).filter(ChargeRequest.id == record.id).update({
            "charge_mode": charge_mode,
            "require_amount": require_amount,
            "charge_id": charge_id
        })
        session.commit()
        success = True
        error_msg = None
    else:
        success = False
        error_msg = "修改失败，车辆不在等候区。"
    if success:
        return json({
            "code": 0,
            "message": "Success"
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })


@app.get('/user/end_charging_request')
@authorized()
async def end_charging_request(request):
    user = session.query(User).filter(User.username == get_username(request)).first()
    # TODO(2): 处理，取消充电请求
    # 生成详单
    # 更新状态
    # 触发调度
    success = None
    error_msg = None
    if success:
        return json({
            "code": 0,
            "message": "Success"
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })

@app.get('/user/query_order_detail')
@authorized()
async def query_order_detail(request):
    user = session.query(User).filter(User.username == get_username(request)).first()
    # TODO(2): 处理，获取该用户所有充电详单
    # 读取数据库
    success = None
    error_msg = None
    order_list = None
    if success:
        return json({
            "code": 0,
            "message": "Success",
            "data": order_list
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })

@app.get('/user/preview_queue')
@authorized()
async def preview_queue(request):
    user = session.query(User).filter(User.username == get_username(request)).first()
    # TODO(1): 处理，获取排队详情
    # 读取数据库
    record = session.query(ChargeRequest).filter(ChargeRequest.user_id == user.id and ChargeRequest.state in [1,2,3,4,5]).first()
    # 若存在还未结束的充电请求
    if record is not None:
        charge_id = record.charge_id
        info = ['', "WAITINGSTAGE1","WAITINGSTAGE2","CHARGING"]
        cur_state = info[record.state]
        if record.state == 1:
            place = "WAITINGPLACE"
        elif record.state in [2,3]:
            place = record.charge_pile_id
        else:
            place = None
        # 算前方车辆
        if record.state == 1:
            num_wait = session.query(WaitQueue).filter(WaitQueue.type == record.charge_mode and WaitQueue.state == 1).count()
            charge_mode_piles = session.query(Charger).filter(Charger.type == record.charge_mode).all()
            num_charge_wait = 0
            for pile in charge_mode_piles:
                num_charge_wait = num_charge_wait + len(pile.charge_list)
            queue_len = num_wait + num_charge_wait
        elif record.state == 2:
            # queue_len = 对应record.charge_pile_id充电桩前面车的数量
            charge_pile = session.query(Charger).filter(Charger.id == record.charge_pile_id).first()
            queue_len = len(charge_pile.charge_list)
        elif record.state == 3:
            queue_len = 0
        else:
            queue_len = None
    else:
        cur_state = "NOTCHARGING"
        charge_id = None
        queue_len = None
        cur_state = None
        place = None
    success = True
    error_msg = None
    # success = None
    # error_msg = None
    # charge_id = None
    # queue_len = None
    # cur_state = None
    # place = None
    if success:
        return json({
            "code": 0,
            "message": "Success",
            "data": {
                "charge_id": charge_id,
                "queue_len": queue_len,
                "cur_state": cur_state,
                "place": place
            }
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })

@app.get('/admin/query_report')
@authorized_admin()
async def query_report(request):
    # TODO(3): 处理，获取充电站的数据报表列表
    # 读取数据库
    # 用报表计算结果
    success = None
    error_msg = None
    report_list = None
    if success:
        return json({
            "code": 0,
            "message": "Success",
            "data": report_list
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })

@app.get('/admin/query_all_piles_stat')
@authorized_admin()
async def query_all_piles_stat(request):
    # TODO(2): 处理，获取所有充电桩的统计信息
    # 读取数据库
    success = None
    error_msg = None
    stat_list = None
    if success:
        return json({
            "code": 0,
            "message": "Success",
            "data": stat_list
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })

@app.get('/admin/query_queue')
@authorized_admin()
async def query_queue(request):
    # TODO(3): 处理，获取目前所有正在排队的用户
    # 读取数据库
    success = None
    error_msg = None
    queue_list = None
    if success:
        return json({
            "code": 0,
            "message": "Success",
            "data": queue_list
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })

@app.post('/admin/update_pile')
@json_validate(update_pile_json_schema)
@authorized_admin()
async def update_pile(request):
    pile_id = request.json.get('pile_id')
    status = request.json.get('status')
    # TODO(3): 处理，更新充电桩状态
    # 写数据库
    # 触发调度
    success = None
    error_msg = None
    if success:
        return json({
            "code": 0,
            "message": "Success"
        })
    else:
        return json({
            "code": -1,
            "message": error_msg
        })
