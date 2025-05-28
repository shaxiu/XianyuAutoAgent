if (typeof atob === 'undefined') {
  global.atob = function(str) {
    return Buffer.from(str, 'base64').toString('binary');
  }
}

const crypto = require('crypto')

const generate_mid = () => {
    return "" + Math.floor(1e3 * Math.random()) + new Date().getTime() + " 0"
}

const generate_uuid = () => {
    return "-" + Date.now() + "1"
}

const generate_device_id = (user_id) => {
    for (var ee, et = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz".split(""), en = [], eo = Math.random, ei = 0; ei < 36; ei++)
        8 === ei || 13 === ei || 18 === ei || 23 === ei ? en[ei] = "-" : 14 === ei ? en[ei] = "4" : (ee = 0 | 16 * eo(),
            en[ei] = et[19 === ei ? 3 & ee | 8 : ee]);
    return en.join("") + "-" + user_id
}


const generate_sign = (t, token, data) => {
    const j = t
    const h = 34839810
    const msg = token + "&" + j + "&" + h + "&" + data
    const md5 = crypto.createHash('md5')
    md5.update(msg)
    return md5.digest('hex')
}
eM = new TextDecoder("utf-8");
eL = null
var sv = Array(4096);

function sg() {
    var ee, et = eI[aG++];
    if (!(et >= 160) || !(et < 192))
        return aG--,
            sy(a5());
    if (et -= 160,
    aX >= aG)
        return eR.slice(aG - aq, (aG += et) - aq);
    if (!(0 == aX && eO < 180))
        return se(et);
    var en = (et << 5 ^ (et > 1 ? eZ.getUint16(aG) : et > 0 ? eI[aG] : 0)) & 4095
        , eo = sv[en]
        , ei = aG
        , ec = aG + et - 3
        , eu = 0;
    if (eo && eo.bytes == et) {
        for (; ei < ec;) {
            if ((ee = eZ.getUint32(ei)) != eo[eu++]) {
                ei = 1879048192;
                break
            }
            ei += 4
        }
        for (ec += 3; ei < ec;)
            if ((ee = eI[ei++]) != eo[eu++]) {
                ei = 1879048192;
                break
            }
        if (ei === ec)
            return aG = ei,
                eo.string;
        ec -= 3,
            ei = aG
    }
    for (eo = [],
             sv[en] = eo,
             eo.bytes = et; ei < ec;)
        ee = eZ.getUint32(ei),
            eo.push(ee),
            ei += 4;
    for (ec += 3; ei < ec;)
        ee = eI[ei++],
            eo.push(ee);
    var ed = et < 16 ? su(et) : sl(et);
    return null != ed ? eo.string = ed : eo.string = se(et)
}

function sy(ee) {
    if ("string" == typeof ee)
        return ee;
    if ("number" == typeof ee || "boolean" == typeof ee || "bigint" == typeof ee)
        return ee.toString();
    if (null == ee)
        return ee + "";
    throw Error("Invalid property type for record", typeof ee)
}

r9 = function (ee) {
    return atob(rW(ee))
}
rW = function (ee) {
    return ee.replace(/[^A-Za-z0-9\+\/]/g, "")
}
aW = {
    "useRecords": false,
    "mapsAsObjects": true
}
aJ = false
eP = []

function a3(ee) {
    if (!aW.trusted && !aJ) {
        var et, en, eo = eP.sharedLength || 0;
        eo < eP.length && (eP.length = eo)
    }
    if (aW.randomAccessStructure && eI[aG] < 64 && eI[aG] >= 32 && ej ? (et = ej(eI, aG, eO, aW),
        eI = null,
    !(ee && ee.lazy) && et && (et = et.toJSON()),
        aG = eO) : et = a5(),
    eD && (aG = eD.postBundlePosition,
        eD = null),
    aJ && (eP.restoreStructures = null),
    aG == eO)
        eP && eP.restoreStructures && a4(),
            eP = null,
            eI = null,
        eL && (eL = null);
    else if (aG > eO)
        throw Error("Unexpected end of MessagePack data");
    else if (!aJ) {
        try {
            en = JSON.stringify(et, function (ee, et) {
                return "bigint" == typeof et ? "".concat(et, "n") : et
            }).slice(0, 100)
        } catch (ee) {
            en = "(JSON view not available " + ee + ")"
        }
        throw Error("Data read, but end of buffer not reached " + en)
    }
    return et

}

function so(ee) {
    if (ee < 16 && (et = su(ee)))
        return et;
    if (ee > 64 && eM)
        return eM.decode(eI.subarray(aG, aG += ee));
    var et, en = aG + ee, eo = [];
    for (et = ""; aG < en;) {
        var ei = eI[aG++];
        if ((128 & ei) === 0)
            eo.push(ei);
        else if ((224 & ei) === 192) {
            var ec = 63 & eI[aG++];
            eo.push((31 & ei) << 6 | ec)
        } else if ((240 & ei) === 224) {
            var eu = 63 & eI[aG++]
                , ed = 63 & eI[aG++];
            eo.push((31 & ei) << 12 | eu << 6 | ed)
        } else if ((248 & ei) === 240) {
            var ef = (7 & ei) << 18 | (63 & eI[aG++]) << 12 | (63 & eI[aG++]) << 6 | 63 & eI[aG++];
            ef > 65535 && (ef -= 65536,
                eo.push(ef >>> 10 & 1023 | 55296),
                ef = 56320 | 1023 & ef),
                eo.push(ef)
        } else
            eo.push(ei);
        eo.length >= 4096 && (et += sc.apply(String, eo),
            eo.length = 0)
    }
    return eo.length > 0 && (et += sc.apply(String, eo)),
        et
}

se = so;
var sc = String.fromCharCode;

function sl(ee) {
    for (var et = aG, en = Array(ee), eo = 0; eo < ee; eo++) {
        var ei = eI[aG++];
        if ((128 & ei) > 0) {
            aG = et;
            return
        }
        en[eo] = ei
    }
    return sc.apply(String, en)
}

function su(ee) {
    if (ee < 4) {
        if (ee < 2) {
            if (0 === ee)
                return "";
            var et = eI[aG++];
            if ((128 & et) > 1) {
                aG -= 1;
                return
            }
            return sc(et)
        }
        var en = eI[aG++]
            , eo = eI[aG++];
        if ((128 & en) > 0 || (128 & eo) > 0) {
            aG -= 2;
            return
        }
        if (ee < 3)
            return sc(en, eo);
        var ei = eI[aG++];
        if ((128 & ei) > 0) {
            aG -= 3;
            return
        }
        return sc(en, eo, ei)
    }
    var ec = eI[aG++]
        , eu = eI[aG++]
        , ed = eI[aG++]
        , ef = eI[aG++];
    if ((128 & ec) > 0 || (128 & eu) > 0 || (128 & ed) > 0 || (128 & ef) > 0) {
        aG -= 4;
        return
    }
    if (ee < 6) {
        if (4 === ee)
            return sc(ec, eu, ed, ef);
        var ep = eI[aG++];
        if ((128 & ep) > 0) {
            aG -= 5;
            return
        }
        return sc(ec, eu, ed, ef, ep)
    }
    if (ee < 8) {
        var em = eI[aG++]
            , eh = eI[aG++];
        if ((128 & em) > 0 || (128 & eh) > 0) {
            aG -= 6;
            return
        }
        if (ee < 7)
            return sc(ec, eu, ed, ef, em, eh);
        var ev = eI[aG++];
        if ((128 & ev) > 0) {
            aG -= 7;
            return
        }
        return sc(ec, eu, ed, ef, em, eh, ev)
    }
    var eg = eI[aG++]
        , eC = eI[aG++]
        , eS = eI[aG++]
        , ew = eI[aG++];
    if ((128 & eg) > 0 || (128 & eC) > 0 || (128 & eS) > 0 || (128 & ew) > 0) {
        aG -= 8;
        return
    }
    if (ee < 10) {
        if (8 === ee)
            return sc(ec, eu, ed, ef, eg, eC, eS, ew);
        var eE = eI[aG++];
        if ((128 & eE) > 0) {
            aG -= 9;
            return
        }
        return sc(ec, eu, ed, ef, eg, eC, eS, ew, eE)
    }
    if (ee < 12) {
        var ek = eI[aG++]
            , e_ = eI[aG++];
        if ((128 & ek) > 0 || (128 & e_) > 0) {
            aG -= 10;
            return
        }
        if (ee < 11)
            return sc(ec, eu, ed, ef, eg, eC, eS, ew, ek, e_);
        var eT = eI[aG++];
        if ((128 & eT) > 0) {
            aG -= 11;
            return
        }
        return sc(ec, eu, ed, ef, eg, eC, eS, ew, ek, e_, eT)
    }
    var eN = eI[aG++]
        , eM = eI[aG++]
        , eO = eI[aG++]
        , eP = eI[aG++];
    if ((128 & eN) > 0 || (128 & eM) > 0 || (128 & eO) > 0 || (128 & eP) > 0) {
        aG -= 12;
        return
    }
    if (ee < 14) {
        if (12 === ee)
            return sc(ec, eu, ed, ef, eg, eC, eS, ew, eN, eM, eO, eP);
        var eR = eI[aG++];
        if ((128 & eR) > 0) {
            aG -= 13;
            return
        }
        return sc(ec, eu, ed, ef, eg, eC, eS, ew, eN, eM, eO, eP, eR)
    }
    var eD = eI[aG++]
        , eL = eI[aG++];
    if ((128 & eD) > 0 || (128 & eL) > 0) {
        aG -= 14;
        return
    }
    if (ee < 15)
        return sc(ec, eu, ed, ef, eg, eC, eS, ew, eN, eM, eO, eP, eD, eL);
    var eZ = eI[aG++];
    if ((128 & eZ) > 0) {
        aG -= 15;
        return
    }
    return sc(ec, eu, ed, ef, eg, eC, eS, ew, eN, eM, eO, eP, eD, eL, eZ)
}

function ss(ee) {
    if (aW.mapsAsObjects) {
        for (var et = {}, en = 0; en < ee; en++) {
            var eo = sg();
            "__proto__" === eo && (eo = "__proto_"),
                et[eo] = a5()
        }
        return et
    }
    for (var ei = new Map, ec = 0; ec < ee; ec++)
        ei.set(a5(), a5());
    return ei
}

function a5() {
    var ee, et = eI[aG++];
    if (et < 160) {
        if (et < 128) {
            if (et < 64)
                return et;
            var en = eP[63 & et] || aW.getStructures && a9()[63 & et];
            return en ? (en.read || (en.read = a8(en, 63 & et)),
                en.read()) : et
        }
        if (et < 144) {
            if (et -= 128,
                aW.mapsAsObjects) {
                for (var eo = {}, ei = 0; ei < et; ei++) {
                    var ec = sg();
                    "__proto__" === ec && (ec = "__proto_"),
                        eo[ec] = a5()
                }
                return eo
            }
            for (var eu = new Map, ed = 0; ed < et; ed++)
                eu.set(a5(), a5());
            return eu
        }
        for (var ef = Array(et -= 144), ep = 0; ep < et; ep++)
            ef[ep] = a5();
        return aW.freezeData ? Object.freeze(ef) : ef
    }
    if (et < 192) {
        var em = et - 160;
        if (aX >= aG)
            return eR.slice(aG - aq, (aG += em) - aq);
        if (0 == aX && eO < 140) {
            var eh = em < 16 ? su(em) : sl(em);
            if (null != eh)
                return eh
        }
        return se(em)
    }
    switch (et) {
        case 192:
            return null;
        case 193:
            if (eD) {
                if ((ee = a5()) > 0)
                    return eD[1].slice(eD.position1, eD.position1 += ee);
                return eD[0].slice(eD.position0, eD.position0 -= ee)
            }
            return aY;
        case 194:
            return !1;
        case 195:
            return !0;
        case 196:
            if (void 0 === (ee = eI[aG++]))
                throw Error("Unexpected end of buffer");
            return sm(ee);
        case 197:
            return ee = eZ.getUint16(aG),
                aG += 2,
                sm(ee);
        case 198:
            return ee = eZ.getUint32(aG),
                aG += 4,
                sm(ee);
        case 199:
            return sh(eI[aG++]);
        case 200:
            return ee = eZ.getUint16(aG),
                aG += 2,
                sh(ee);
        case 201:
            return ee = eZ.getUint32(aG),
                aG += 4,
                sh(ee);
        case 202:
            if (ee = eZ.getFloat32(aG),
            aW.useFloat32 > 2) {
                var ev = sT[(127 & eI[aG]) << 1 | eI[aG + 1] >> 7];
                return aG += 4,
                (ev * ee + (ee > 0 ? .5 : -.5) >> 0) / ev
            }
            return aG += 4,
                ee;
        case 203:
            return ee = eZ.getFloat64(aG),
                aG += 8,
                ee;
        case 204:
            return eI[aG++];
        case 205:
            return ee = eZ.getUint16(aG),
                aG += 2,
                ee;
        case 206:
            return ee = eZ.getUint32(aG),
                aG += 4,
                ee;
        case 207:
            return "number" === aW.int64AsType ? ee = 4294967296 * eZ.getUint32(aG) + eZ.getUint32(aG + 4) : "string" === aW.int64AsType ? ee = eZ.getBigUint64(aG).toString() : "auto" === aW.int64AsType ? (ee = eZ.getBigUint64(aG)) <= BigInt(2) << BigInt(52) && (ee = Number(ee)) : ee = eZ.getBigUint64(aG),
                aG += 8,
                ee;
        case 208:
            return eZ.getInt8(aG++);
        case 209:
            return ee = eZ.getInt16(aG),
                aG += 2,
                ee;
        case 210:
            return ee = eZ.getInt32(aG),
                aG += 4,
                ee;
        case 211:
            return "number" === aW.int64AsType ? ee = 4294967296 * eZ.getInt32(aG) + eZ.getUint32(aG + 4) : "string" === aW.int64AsType ? ee = eZ.getBigInt64(aG).toString() : "auto" === aW.int64AsType ? (ee = eZ.getBigInt64(aG)) >= BigInt(-2) << BigInt(52) && ee <= BigInt(2) << BigInt(52) && (ee = Number(ee)) : ee = eZ.getBigInt64(aG),
                aG += 8,
                ee;
        case 212:
            if (114 == (ee = eI[aG++]))
                return sC(63 & eI[aG++]);
            var eg = aK[ee];
            if (eg) {
                if (eg.read)
                    return aG++,
                        eg.read(a5());
                if (eg.noBuffer)
                    return aG++,
                        eg();
                return eg(eI.subarray(aG, ++aG))
            }
            throw Error("Unknown extension " + ee);
        case 213:
            if (114 == (ee = eI[aG]))
                return aG++,
                    sC(63 & eI[aG++], eI[aG++]);
            return sh(2);
        case 214:
            return sh(4);
        case 215:
            return sh(8);
        case 216:
            return sh(16);
        case 217:
            if (ee = eI[aG++],
            aX >= aG)
                return eR.slice(aG - aq, (aG += ee) - aq);
            return st(ee);
        case 218:
            if (ee = eZ.getUint16(aG),
                aG += 2,
            aX >= aG)
                return eR.slice(aG - aq, (aG += ee) - aq);
            return sn(ee);
        case 219:
            if (ee = eZ.getUint32(aG),
                aG += 4,
            aX >= aG)
                return eR.slice(aG - aq, (aG += ee) - aq);
            return sr(ee);
        case 220:
            return ee = eZ.getUint16(aG),
                aG += 2,
                si(ee);
        case 221:
            return ee = eZ.getUint32(aG),
                aG += 4,
                si(ee);
        case 222:
            return ee = eZ.getUint16(aG),
                aG += 2,
                ss(ee);
        case 223:
            return ee = eZ.getUint32(aG),
                aG += 4,
                ss(ee);
        default:
            if (et >= 224)
                return et - 256;
            if (void 0 === et) {
                var eC = Error("Unexpected end of MessagePack data");
                throw eC.incomplete = !0,
                    eC
            }
            throw Error("Unknown MessagePack token " + et)
    }
}

sn = so
var a6 = /^[a-zA-Z_$][a-zA-Z\d_$]*$/;
const decrypt = (ee) => {
    for (var et, en, eo = r9(ee), ei = eo.length, ec = new Uint8Array(ei), eu = 0; eu < ei; eu++) {
        var ed = eo.charCodeAt(eu);
        ec[eu] = ed
    }
    en = {}
    et = ec;
    et.buffer || et.constructor !== ArrayBuffer || (et = "undefined" != typeof Buffer ? Buffer.from(et) : new Uint8Array(et)),
        "object" == typeof en ? (eO = en.end || et.length,
            aG = en.start || 0) : (aG = 0,
            eO = en > -1 ? en : et.length),
        aX = 0,
        eR = null,
        eD = null,
        eI = et;
    eM = new TextDecoder("utf-8");
    eL = null

    eP = [];
    eZ = et.dataView || (et.dataView = new DataView(et.buffer, et.byteOffset, et.byteLength))
    res = a3(en)
    // ec = ecc;
    // rA = 0;
    // rB = 0;
    // ed = [];
    // eu = ec.length;
    // rj = {
    //     "useRecords": false,
    //     "mapsAsObjects": true
    // }
    // // ei 是 TextDecoder
    // ei = new TextDecoder("utf-8");
    // eh = new DataView(ec.buffer, ec.byteOffset, ec.byteLength);
    // ec.dataView = eh;
    // let res = rK()
    const replacer = (key, value) => {
        if (typeof value === 'bigint') {
            return value.toString();
        }
        return value;
    };

    res = JSON.stringify(res, replacer);
    return res;
}


// console.log(generate_mid())
// console.log(generate_uuid())
// console.log(generate_device_id())
// console.log(generate_sign('5f65b00f83994987e334f97360d69557', '{"sessionTypes":"1,19"}'))
// let msg = "ggGLAYEBtTIyMDI2NDA5MTgwNzlAZ29vZmlzaAKzNDc4MTI4NzAwMDBAZ29vZmlzaAOxMzQwMjM5MTQ3MjUwMy5QTk0EAAXPAAABlYW04bIGggFlA4UBoAKjMTExA6AEAQXaADR7ImF0VXNlcnMiOltdLCJjb250ZW50VHlwZSI6MSwidGV4dCI6eyJ0ZXh0IjoiMTExIn19BwIIAQkACoupX3BsYXRmb3Jtp2FuZHJvaWSmYml6VGFn2gBBeyJzb3VyY2VJZCI6IlM6MSIsIm1lc3NhZ2VJZCI6ImYzNjkwMmVmZjQ1NDQ1YmRiMmQxYjBmZDE2OGY4MjY0In2sZGV0YWlsTm90aWNlozExMadleHRKc29u2gBLeyJxdWlja1JlcGx5IjoiMSIsIm1lc3NhZ2VJZCI6ImYzNjkwMmVmZjQ1NDQ1YmRiMmQxYjBmZDE2OGY4MjY0IiwidGFnIjoidSJ9r3JlbWluZGVyQ29udGVudKMxMTGucmVtaW5kZXJOb3RpY2W15Y+R5p2l5LiA5p2h5paw5raI5oGvrXJlbWluZGVyVGl0bGWmc2hh5L+uq3JlbWluZGVyVXJs2gCbZmxlYW1hcmtldDovL21lc3NhZ2VfY2hhdD9pdGVtSWQ9ODk3NzQyNzQ4MDExJnBlZXJVc2VySWQ9MjIwMjY0MDkxODA3OSZwZWVyVXNlck5pY2s9dCoqKjEmc2lkPTQ3ODEyODcwMDAwJm1lc3NhZ2VJZD1mMzY5MDJlZmY0NTQ0NWJkYjJkMWIwZmQxNjhmODI2NCZhZHY9bm+sc2VuZGVyVXNlcklkrTIyMDI2NDA5MTgwNzmuc2VuZGVyVXNlclR5cGWhMKtzZXNzaW9uVHlwZaExDAEDgahuZWVkUHVzaKR0cnVl";
//
msg = "ggGLAYEBsjMxNDk2MzcwNjNAZ29vZmlzaAKzNDc5ODMzODkwOTZAZ29vZmlzaAOxMzQxNjU2NTI3NDU0Mi5QTk0EAAXPAAABlbKji20GggFlA4UBoAK6W+aIkeW3suaLjeS4i++8jOW+heS7mOasvl0DoAQaBdoEKnsiY29udGVudFR5cGUiOjI2LCJkeENhcmQiOnsiaXRlbSI6eyJtYWluIjp7ImNsaWNrUGFyYW0iOnsiYXJnMSI6Ik1zZ0NhcmQiLCJhcmdzIjp7InNvdXJjZSI6ImltIiwidGFza19pZCI6IjNleFFKSE9UbVBVMSIsIm1zZ19pZCI6ImNjOGJjMmRmN2M5MzRkZjA4NmUwNTY3Y2I2OWYxNTczIn19LCJleENvbnRlbnQiOnsiYmdDb2xvciI6IiNGRkZGRkYiLCJidXR0b24iOnsiYmdDb2xvciI6IiNGRkU2MEYiLCJib3JkZXJDb2xvciI6IiNGRkU2MEYiLCJjbGlja1BhcmFtIjp7ImFyZzEiOiJNc2dDYXJkQWN0aW9uIiwiYXJncyI6eyJzb3VyY2UiOiJpbSIsInRhc2tfaWQiOiIzZXhRSkhPVG1QVTEiLCJtc2dfaWQiOiJjYzhiYzJkZjdjOTM0ZGYwODZlMDU2N2NiNjlmMTU3MyJ9fSwiZm9udENvbG9yIjoiIzMzMzMzMyIsInRhcmdldFVybCI6ImZsZWFtYXJrZXQ6Ly9hZGp1c3RfcHJpY2U/Zmx1dHRlcj10cnVlJmJpek9yZGVySWQ9MjUwMzY4ODEyNjM1NjYzNjM3MCIsInRleHQiOiLkv67mlLnku7fmoLwifSwiZGVzYyI6Iuivt+WPjOaWueayn+mAmuWPiuaXtuehruiupOS7t+agvCIsImRlc2NDb2xvciI6IiNBM0EzQTMiLCJ0aXRsZSI6IuaIkeW3suaLjeS4i++8jOW+heS7mOasviIsInVwZ3JhZGUiOnsidGFyZ2V0VXJsIjoiaHR0cHM6Ly9oNS5tLmdvb2Zpc2guY29tL2FwcC9pZGxlRmlzaC1GMmUvZm0tZG93bmxhb2QvaG9tZS5odG1sP25vUmVkcmllY3Q9dHJ1ZSZjYW5CYWNrPXRydWUmY2hlY2tWZXJzaW9uPXRydWUiLCJ2ZXJzaW9uIjoiNy43LjkwIn19LCJ0YXJnZXRVcmwiOiJmbGVhbWFya2V0Oi8vb3JkZXJfZGV0YWlsP2lkPTI1MDM2ODgxMjYzNTY2MzYzNzAmcm9sZT1zZWxsZXIifX0sInRlbXBsYXRlIjp7Im5hbWUiOiJpZGxlZmlzaF9tZXNzYWdlX3RyYWRlX2NoYXRfY2FyZCIsInVybCI6Imh0dHBzOi8vZGluYW1pY3guYWxpYmFiYXVzZXJjb250ZW50LmNvbS9wdWIvaWRsZWZpc2hfbWVzc2FnZV90cmFkZV9jaGF0X2NhcmQvMTY2NzIyMjA1Mjc2Ny9pZGxlZmlzaF9tZXNzYWdlX3RyYWRlX2NoYXRfY2FyZC56aXAiLCJ2ZXJzaW9uIjoiMTY2NzIyMjA1Mjc2NyJ9fX0HAQgBCQAK3gAQpmJpelRhZ9oAe3sic291cmNlSWQiOiJDMkM6M2V4UUpIT1RtUFUxIiwidGFza05hbWUiOiLlt7Lmi43kuItf5pyq5LuY5qy+X+WNluWutiIsIm1hdGVyaWFsSWQiOiIzZXhRSkhPVG1QVTEiLCJ0YXNrSWQiOiIzZXhRSkhPVG1QVTEifbFjbG9zZVB1c2hSZWNlaXZlcqVmYWxzZbFjbG9zZVVucmVhZE51bWJlcqVmYWxzZaxkZXRhaWxOb3RpY2W6W+aIkeW3suaLjeS4i++8jOW+heS7mOasvl2nZXh0SnNvbtoBr3sibXNnQXJncyI6eyJ0YXNrX2lkIjoiM2V4UUpIT1RtUFUxIiwic291cmNlIjoiaW0iLCJtc2dfaWQiOiJjYzhiYzJkZjdjOTM0ZGYwODZlMDU2N2NiNjlmMTU3MyJ9LCJxdWlja1JlcGx5IjoiMSIsIm1zZ0FyZzEiOiJNc2dDYXJkIiwidXBkYXRlS2V5IjoiNDc5ODMzODkwOTY6MjUwMzY4ODEyNjM1NjYzNjM3MDoxX25vdF9wYXlfc2VsbGVyIiwibWVzc2FnZUlkIjoiY2M4YmMyZGY3YzkzNGRmMDg2ZTA1NjdjYjY5ZjE1NzMiLCJtdWx0aUNoYW5uZWwiOnsiaHVhd2VpIjoiRVhQUkVTUyIsInhpYW9taSI6IjEwODAwMCIsIm9wcG8iOiJFWFBSRVNTIiwiaG9ub3IiOiJOT1JNQUwiLCJhZ29vIjoicHJvZHVjdCIsInZpdm8iOiJPUkRFUiJ9LCJjb250ZW50VHlwZSI6IjI2IiwiY29ycmVsYXRpb25Hcm91cElkIjoiM2V4UUpIT1RtUFUxX0ZGcjRHT1NuOE9RbyJ9qHJlY2VpdmVyrTIyMDI2NDA5MTgwNzmrcmVkUmVtaW5kZXKy562J5b6F5Lmw5a625LuY5qy+sHJlZFJlbWluZGVyU3R5bGWhMa9yZW1pbmRlckNvbnRlbnS6W+aIkeW3suaLjeS4i++8jOW+heS7mOasvl2ucmVtaW5kZXJOb3RpY2W75Lmw5a625bey5ouN5LiL77yM5b6F5LuY5qy+rXJlbWluZGVyVGl0bGW75Lmw5a625bey5ouN5LiL77yM5b6F5LuY5qy+q3JlbWluZGVyVXJs2gCaZmxlYW1hcmtldDovL21lc3NhZ2VfY2hhdD9pdGVtSWQ9OTAwMDUyNjQ0Mjc3JnBlZXJVc2VySWQ9MzE0OTYzNzA2MyZwZWVyVXNlck5pY2s955S3KioqeSZzaWQ9NDc5ODMzODkwOTYmbWVzc2FnZUlkPWNjOGJjMmRmN2M5MzRkZjA4NmUwNTY3Y2I2OWYxNTczJmFkdj1ub6xzZW5kZXJVc2VySWSqMzE0OTYzNzA2M65zZW5kZXJVc2VyVHlwZaEwq3Nlc3Npb25UeXBloTGqdXBkYXRlSGVhZKR0cnVlDAEDgahuZWVkUHVzaKR0cnVl"
msg = "hAGzNDc5ODMzODkwOTZAZ29vZmlzaAIBA4KrcmVkUmVtaW5kZXKy562J5b6F5Lmw5a625LuY5qy+sHJlZFJlbWluZGVyU3R5bGWhMQTPAAABlbMlNng="
res = decrypt(msg);
console.log(res);
