#! /usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# http://www.indigodomo.com

import indigo
import threading
import Queue
import time
from datetime import datetime, timedelta
from ast import literal_eval
from collections import OrderedDict

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

###############################################################################
# globals

k_commonTrueStates = ['true', 'on', 'open', 'up', 'yes', 'active', 'locked', '1']

k_stateImages = {
    'SensorOff':    indigo.kStateImageSel.SensorOff,
    'TimerOff':     indigo.kStateImageSel.TimerOff,
    'SensorOn':     indigo.kStateImageSel.SensorOn,
    'TimerOn':      indigo.kStateImageSel.TimerOn,
    }

k_deviceKeys = (
    ('device1', 'state1'),
    ('device2', 'state2'),
    ('device3', 'state3'),
    ('device4', 'state4'),
    ('device5', 'state5'),
    ('device6', 'state6'),
    ('device7', 'state7'),
    ('device8', 'state8'),
    ('device9', 'state9'),
    ('device10', 'state10'),
    ('device11', 'state11'),
    ('device12', 'state12'),
    ('device13', 'state13'),
    ('device14', 'state14'),
    ('device15', 'state15'),
    ('device16', 'state16'),
    ('device17', 'state17'),
    ('device18', 'state18'),
    ('device19', 'state19'),
    ('device20', 'state20'),
    )

k_variableKeys = (
    'variable1',
    'variable2',
    'variable3',
    'variable4',
    'variable5',
    'variable6',
    'variable7',
    'variable8',
    'variable9',
    'variable10',
    )

k_timeSpans = OrderedDict([
    ('h', 'Hour'),
    ('d', 'Day'),
    ('w', 'Week'),
    ('m', 'Month'),
    ('y', 'Year'),
    ('c', 'Continuous'),
    ])

k_periodRange = {
    'h': 25,
    'd': 8,
    'w': 5,
    'm': 13,
    'y': 2,
    'c': 2,
    }

k_tickSeconds = 1

k_strftimeFormat = '%Y-%m-%d %H:%M:%S'

################################################################################
class Plugin(indigo.PluginBase):
    #-------------------------------------------------------------------------------
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.configDeviceList = list()
        self.configVariableList = list()

    def __del__(self):
        indigo.PluginBase.__del__(self)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.showTimer  = self.pluginPrefs.get('showTimer',False)
        self.debug      = self.pluginPrefs.get('showDebugInfo',False)
        self.verbose    = self.pluginPrefs.get('verboseDebug',False) and self.debug
        self.logger.debug("startup")
        if self.debug:
            self.logger.debug("Debug logging enabled")

        self.deviceDict = dict()
        self.tickTime   = time.time()

        indigo.devices.subscribeToChanges()
        indigo.variables.subscribeToChanges()

    #-------------------------------------------------------------------------------
    def shutdown(self):
        self.logger.debug("shutdown")
        self.pluginPrefs['showDebugInfo']   = self.debug
        self.pluginPrefs['verboseDebug']    = self.verbose
        self.pluginPrefs['showTimer']       = self.showTimer

    #-------------------------------------------------------------------------------
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.debug("validatePrefsConfigUi")
        errorsDict = indigo.Dict()

        if len(errorsDict) > 0:
            self.logger.debug('validate prefs config error: \n{}'.format(errorsDict))
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    #-------------------------------------------------------------------------------
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug("closedPrefsConfigUi")
        if not userCancelled:
            self.debug     = valuesDict.get('showDebugInfo',False)
            self.verbose   = valuesDict.get('verboseDebug',False) and self.debug
            self.showTimer = valuesDict.get('showTimer',True)
            if self.debug:
                self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    def runConcurrentThread(self):
        try:
            while True:
                self.tickTime = time.time()
                for device in self.deviceDict.values():
                    device.doTask('tick')
                self.sleep(self.tickTime + k_tickSeconds - time.time())
        except self.StopThread:
            pass    # Optionally catch the StopThread exception and do any needed cleanup.

    #-------------------------------------------------------------------------------
    # Device Methods
    #-------------------------------------------------------------------------------
    def deviceStartComm(self, dev):
        if dev.version != self.pluginVersion:
            self.updateDeviceVersion(dev)
        if dev.configured:
            if dev.deviceTypeId == 'activityTimer':
                self.deviceDict[dev.id] = ActivityTimer(dev, self)
            elif dev.deviceTypeId == 'thresholdTimer':
                self.deviceDict[dev.id] = ThresholdTimer(dev, self)
            elif dev.deviceTypeId == 'persistenceTimer':
                self.deviceDict[dev.id] = PersistenceTimer(dev, self)
            elif dev.deviceTypeId == 'lockoutTimer':
                self.deviceDict[dev.id] = LockoutTimer(dev, self)
            elif dev.deviceTypeId == 'aliveTimer':
                self.deviceDict[dev.id] = AliveTimer(dev, self)
            elif dev.deviceTypeId == 'runningTimer':
                self.deviceDict[dev.id] = RunningTimer(dev, self)
            # start the thread
            self.deviceDict[dev.id].start()

    #-------------------------------------------------------------------------------
    def deviceStopComm(self, dev):
        if dev.id in self.deviceDict:
            self.deviceDict[dev.id].cancel()
            while self.deviceDict[dev.id].is_alive():
                time.sleep(0.1)
            del self.deviceDict[dev.id]

    #-------------------------------------------------------------------------------
    def validateDeviceConfigUi(self, valuesDict, typeId, devId, runtime=False):
        self.logger.debug("validateDeviceConfigUi: " + typeId)
        errorsDict = indigo.Dict()

        requiredIntegers = ['offCycles']
        if typeId == 'activityTimer':
            requiredIntegers = ['offCycles','resetCycles','countThreshold']

        elif typeId == 'activityTimer':
            requiredIntegers = ['offCycles','countThreshold']

        elif typeId in ['persistenceTimer','lockoutTimer']:
            requiredIntegers = ['offCycles','onCycles']
            if valuesDict.get('trackEntity','dev') == 'dev':
                keys = k_deviceKeys[0]
            else:
                keys = [k_variableKeys[0]]
            for key in keys:
                if not valuesDict.get(key,''):
                    errorsDict[key] = "Required"

        elif typeId == 'aliveTimer':
            requiredIntegers = ['offCycles']
            if valuesDict.get('trackEntity','dev') == 'dev':
                key = k_deviceKeys[0][0]
            else:
                key = k_variableKeys[0]
            if not valuesDict.get(key,''):
                errorsDict[key] = "Required"

        elif typeId == 'runningTimer':
            requiredIntegers = []
            if valuesDict.get('trackEntity','dev') == 'dev':
                key = k_deviceKeys[0][0]
            else:
                key = k_variableKeys[0]
            if not valuesDict.get(key,''):
                errorsDict[key] = "Required"

        for key in requiredIntegers:
            if not valuesDict.get(key,"").isdigit():
                errorsDict[key] = "Must be an integer zero or greater"

        for devKey, stateKey in k_deviceKeys:
            if zint(valuesDict.get(devKey,'')) and not valuesDict.get(stateKey,''):
                errorsDict[stateKey] = "Required"

        if valuesDict.get('logicType','simple') == 'complex':
            if valuesDict.get('valueType','str') == 'num':
                try:
                    temp = float(valuesDict.get('value',''))
                except:
                    errorsDict['value'] = "Make value a number or change data type"

        if len(errorsDict) > 0:
            self.logger.debug('validate device config error: \n{}'.format(errorsDict))
            return (False, valuesDict, errorsDict)
        else:
            # on success, reset generated device and variable lists
            self.configDeviceList = list()
            self.configVariableList = list()
            return (True, valuesDict)

    #-------------------------------------------------------------------------------
    def updateDeviceVersion(self, dev):
        theProps = dev.pluginProps
        # update states
        dev.stateListOrDisplayStateIdChanged()

        # update logic selections
        if ver(theProps.get('version',"0.0.0")) < ver("0.0.9"):
            if theProps.get('anyChange',False):
                theProps['logicType'] = 'any'
            else:
                theProps['logicType'] = 'simple'

        # update running timer prior periods
        if ver(theProps.get('version',"0.0.0")) < ver("0.0.22"):
            if dev.deviceTypeId == 'runningTimer':
                newStates = []
                for span, name in k_timeSpans.items():
                    newKey = 'seconds{}00'.format(name)
                    oldKey = 'secondsThis{}'.format(name)
                    newStates.append({'key':newKey, 'value':dev.states[oldKey]})
                    newKey = 'seconds{}01'.format(name)
                    oldKey = 'secondsLast{}'.format(name)
                    newStates.append({'key':newKey, 'value':dev.states[oldKey]})
                dev.updateStatesOnServer(newStates)

        # push to server
        theProps["version"] = self.pluginVersion
        dev.replacePluginPropsOnServer(theProps)

    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):

        if newDev.pluginId == self.pluginId:
            # device belongs to plugin
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)
            if (newDev.id in self.deviceDict) and (newDev.name != oldDev.name):
                # I hate it when the log continues to use an old name
                self.deviceDict[newDev.id].name = newDev.name

        # plugin devices may belong to other plugin devices
        for device in self.deviceDict.values():
            device.doTask('devChanged', oldDev, newDev)

    #-------------------------------------------------------------------------------
    # Variable Methods
    #-------------------------------------------------------------------------------
    def variableUpdated(self, oldVar, newVar):
        for devId, device in self.deviceDict.items():
            device.doTask('varChanged', oldVar, newVar)

    #-------------------------------------------------------------------------------
    # Action Methods
    #-------------------------------------------------------------------------------
    def forceOn(self, action):
        if action.deviceId in self.deviceDict:
            self.deviceDict[action.deviceId].doTask('turnOn')
        else:
            self.logger.error('device id "{}" not available'.format(action.deviceId))

    #-------------------------------------------------------------------------------
    def forceOff(self, action):
        if action.deviceId in self.deviceDict:
            self.deviceDict[action.deviceId].doTask('turnOff')
        else:
            self.logger.error('device id "{}" not available'.format(action.deviceId))

    #-------------------------------------------------------------------------------
    # Menu Methods
    #-------------------------------------------------------------------------------
    def toggleCountdown(self):
        if self.showTimer:
            self.logger.info("visible countdown timer diabled")
            self.showTimer = False
        else:
            self.showTimer = True
            self.logger.info("visible countdown timer enabled")

    #-------------------------------------------------------------------------------
    def toggleDebug(self):
        if self.debug:
            self.logger.debug("Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    # Callbacks
    #-------------------------------------------------------------------------------
    def getDeviceList(self, filter='', valuesDict=dict(), typeId='', targetId=0):
        if self.verbose:
            self.logger.debug('getDeviceList: {}'.format(targetId))

        if not self.configDeviceList:
            # generate device list once
            for dev in indigo.devices.iter():
                if not dev.id == targetId:
                    self.configDeviceList.append((dev.id, dev.name))
            self.configDeviceList.append((0,"- none -"))

        return self.configDeviceList

    #-------------------------------------------------------------------------------
    def getStateList(self, filter=None, valuesDict=dict(), typeId='', targetId=0):
        if self.verbose:
            self.logger.debug('getStateList: {}'.format(targetId))
        stateList = list()
        devId = zint(valuesDict.get(filter,''))
        if devId:
            for state in indigo.devices[devId].states:
                stateList.append((state,state))
        return stateList

    #-------------------------------------------------------------------------------
    def getVariableList(self, filter='', valuesDict=dict(), typeId='', targetId=0):
        if self.verbose:
            self.logger.debug('getVariableList: {}'.format(targetId))

        if not self.configVariableList:
            # generate variable list once
            self.configVariableList = [(var.id,var.name) for var in indigo.variables.iter()]
            self.configVariableList.append((0,"- none -"))

        return self.configVariableList

    #-------------------------------------------------------------------------------
    def loadStates(self, valuesDict=None, typeId='', targetId=0):
        pass

################################################################################
# Classes
################################################################################
class TimerBase(threading.Thread):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(TimerBase, self).__init__()
        self.daemon     = True
        self.cancelled  = False
        self.queue      = Queue.Queue()

        self.plugin     = plugin
        self.logger     = plugin.logger

        self.dev        = instance
        self.id         = instance.id
        self.name       = instance.name
        self.states     = instance.states
        self.stateImg   = None

        self.logic      = instance.pluginProps.get('logicType','simple')
        self.reverse    = instance.pluginProps.get('reverseBoolean',False)
        self.valType    = instance.pluginProps.get('valueType','str')
        self.operator   = instance.pluginProps.get('operator','eq')
        if self.logic == 'complex' and self.valType == 'num':
            self.value = float(instance.pluginProps.get('value',''))
        else:
            self.value = str(instance.pluginProps.get('value','')).lower()

        self.logOnOff   = instance.pluginProps.get('logOnOff',True)

        self.deviceStateDict = dict()
        for deviceKey, stateKey in k_deviceKeys:
            if zint(instance.pluginProps.get(deviceKey,'')):
                self.deviceStateDict[int(instance.pluginProps[deviceKey])] = instance.pluginProps[stateKey]

        self.variableList = list()
        for variableKey in k_variableKeys:
            if zint(instance.pluginProps.get(variableKey,'')):
                self.variableList.append(int(instance.pluginProps[variableKey]))

        self.taskTime = time.time()

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _stateGet(self):
        return self.states['state']
    def _stateSet(self, value):
        self.states['state'] = value
    state = property(_stateGet, _stateSet)

    def _displayStateGet(self):
        return self.states['displayState']
    def _displayStateSet(self, value):
        self.states['displayState'] = value
    displayState = property(_displayStateGet, _displayStateSet)

    def _onStateGet(self):
        return self.states['onOffState']
    def _onStateSet(self, value):
        self.states['onOffState'] = value
    onState = property(_onStateGet, _onStateSet)

    #-------------------------------------------------------------------------------
    def run(self):
        self.logger.debug('"{}" thread started'.format(self.name))
        while not self.cancelled:
            try:
                task,arg1,arg2 = self.queue.get(True,5)
                self.taskTime = time.time()
                if task == 'tick':
                    self.tick()
                elif task == 'tock':
                    self.tock(arg1)
                elif task == 'devChanged':
                    self.devChanged(arg1,arg2)
                elif task == 'varChanged':
                    self.varChanged(arg1,arg2)
                elif task == 'turnOn':
                    self.turnOn()
                elif task == 'turnOff':
                    self.turnOff()
                elif task == 'cancel':
                    self.cancelled = True
                else:
                    self.logger.error('"{}" task "{}" not recognized'.format(self.name,task))
                self.queue.task_done()
            except Queue.Empty:
                pass
            except Exception as e:
                msg = '"{}" thread error \n{}'.format(self.name, e)
                if self.plugin.debug:
                    self.logger.exception(msg)
                else:
                    self.logger.error(msg)
        else:
            self.logger.debug('"{}" thread cancelled'.format(self.name))

    #-------------------------------------------------------------------------------
    def cancel(self):
        """End this thread"""
        self.doTask('cancel')

    #-------------------------------------------------------------------------------
    def doTask(self, task, arg1=None, arg2=None):
        self.queue.put((task, arg1, arg2))

    #-------------------------------------------------------------------------------
    def devChanged(self, oldDev, newDev):
        if newDev.id in self.deviceStateDict:
            stateKey = self.deviceStateDict[newDev.id]
            if oldDev.states[stateKey] != newDev.states[stateKey]:
                rawVal = newDev.states[stateKey]
                boolVal = self.getBoolValue(rawVal)
                if self.plugin.verbose:
                    self.logger.debug('"{}" devChanged:"{}" [stateKey:{}, raw:{}, type:{}, input:{}]'
                        .format(self.name, newDev.name, stateKey, rawVal, type(rawVal), boolVal))
                self.tock(boolVal)

    #-------------------------------------------------------------------------------
    def varChanged(self, oldVar, newVar):
        if newVar.id in self.variableList:
            if oldVar.value != newVar.value:
                rawVal = newVar.value
                boolVal = self.getBoolValue(rawVal)
                if self.plugin.verbose:
                    self.logger.debug('"{}" varChanged:"{}" [raw:{}, type:{}, input:{}]'
                        .format(self.name, newVar.name, rawVal, type(rawVal), boolVal))
                self.tock(boolVal)

    #-------------------------------------------------------------------------------
    def update(self):
        if self.plugin.showTimer or (self.states != self.dev.states):

            self.getStates()

            newStates = list()
            for key, value in self.states.iteritems():
                if self.states[key] != self.dev.states[key]:
                    newStates.append({'key':key,'value':value})
                    if key == 'onOffState' and self.logOnOff:
                        self.logger.info('"{0}" {1}'.format(self.name, ['off','on'][value]))
                    elif key == 'state':
                        self.dev.updateStateImageOnServer(k_stateImages[self.stateImg])

            if self.plugin.verbose:
                logStates = ', '.join('{}:{}'.format(item['key'],item['value']) for item in newStates)
                self.logger.debug('"{0}" states: [{1}]'.format(self.name, logStates.strip(', ')))

            self.dev.updateStatesOnServer(newStates)
            self.states = self.dev.states

    #-------------------------------------------------------------------------------
    def getBoolValue(self, value):
        if self.logic == 'any':
            result = True
        elif self.logic == 'simple':
            result = False
            if zint(value):
                result = True
            elif isinstance(value, basestring):
                result = value.lower() in k_commonTrueStates
            if self.reverse:
                result = not result
        elif self.logic == 'complex':
            try:
                if self.valType == 'str':
                    value = str(value).lower()
                elif self.valType == 'num':
                    value = float(value)
                if   self.operator == 'eq':
                    result = value == self.value
                elif self.operator == 'ne':
                    result = value != self.value
                elif self.operator == 'gt':
                    result = value >  self.value
                elif self.operator == 'lt':
                    result = value <  self.value
                elif self.operator == 'ge':
                    result = value >= self.value
                elif self.operator == 'le':
                    result = value <= self.value
            except ValueError as e:
                result = False
                self.logger.debug('Data type error for device "{}"'.format(self.name))
        return result

    #-------------------------------------------------------------------------------
    def delta(self, cycles, units):
        multiplier = 1
        if units == 'minutes':
            multiplier = 60
        elif units == 'hours':
            multiplier = 60*60
        elif units == 'days':
            multiplier = 60*60*24
        return int(cycles)*multiplier

    #-------------------------------------------------------------------------------
    # abstract methods
    #-------------------------------------------------------------------------------
    def tick(self):
        raise NotImplementedError

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        raise NotImplementedError

    #-------------------------------------------------------------------------------
    def turnOn(self):
        raise NotImplementedError

    #-------------------------------------------------------------------------------
    def turnOff(self):
        raise NotImplementedError

    #-------------------------------------------------------------------------------
    def getStates(self):
        raise NotImplementedError

################################################################################
class ActivityTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(ActivityTimer, self).__init__(instance, plugin)

        self.threshold  = int(instance.pluginProps.get('countThreshold',1))
        self.extend     = instance.pluginProps.get('extend',True)
        self.resetDelta = self.delta( instance.pluginProps.get('resetCycles',1),
                                      instance.pluginProps.get('resetUnits','minutes') )
        self.offDelta   = self.delta( instance.pluginProps.get('offCycles', 10),
                                      instance.pluginProps.get('offUnits',  'minutes') )

        # initial state
        self.tick()

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _offTimeGet(self):
        return self.states['offTime']
    def _offTimeSet(self, value):
        self.states['offTime'] = value
        self.states['offString'] = format_datetime(value)
    offTime = property(_offTimeGet, _offTimeSet)

    def _countGet(self):
        return self.states['count']
    def _countSet(self, value):
        self.states['count'] = value
        self.states['counting'] = bool(value)
    count = property(_countGet, _countSet)

    def _resetGet(self):
        return self.states['reset']
    def _resetSet(self, value):
        self.states['reset'] = value
    reset = property(_resetGet, _resetSet)

    def _expiredGet(self):
        return self.states['expired']
    def _expiredSet(self, value):
        self.states['expired'] = value
    expired = property(_expiredGet, _expiredSet)

    def _resetTimeGet(self):
        return self.states['resetTime']
    def _resetTimeSet(self, value):
        self.states['resetTime'] = value
        self.states['resetString'] = format_datetime(value)
    resetTime = property(_resetTimeGet, _resetTimeSet)

    #-------------------------------------------------------------------------------
    def tick(self):
        reset = expired = False
        if self.count and (self.taskTime >= self.resetTime):
            self.count = 0
            self.reset = True
            logTimer = 'resetTime'
        if self.onState and (self.taskTime >= self.offTime):
            self.onState = False
            self.expired = True
            logTimer = 'offTime'
        if reset or expired:
            self.logger.debug('"{}" timer:{} [onOff:{}, count:{}, reset:{}, expired:{}]'
                .format(self.name, logTimer, self.onState, self.count, self.reset, self.expired))
        self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        if newVal:
            self.count += 1
            self.resetTime = self.taskTime + self.resetDelta
            if self.count >= self.threshold:
                self.onState = True
                self.offTime = self.taskTime + self.offDelta
            elif self.onState and self.extend:
                self.offTime = self.taskTime + self.offDelta
        self.logger.debug('"{}" input:{} [onOff:{}, count:{}, reset:{}, expired:{}]'
            .format(self.name, newVal, self.onState, self.count, self.reset, self.expired))
        self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.onState = True
        self.offTime = self.taskTime + self.offDelta
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        if self.count:
            self.count = 0
            self.resetTime = self.taskTime
        if self.onState:
            self.onState = False
            self.offTime = self.taskTime
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.onState:
            if (self.count >= self.threshold) or (self.count and self.extend):
                self.state = 'active'
                self.stateImg = 'SensorOn'
            else:
                self.state = 'persist'
                self.stateImg = 'TimerOn'
        else:
            if self.count:
                self.state = 'accrue'
                self.stateImg = 'TimerOff'
            else:
                self.state = 'idle'
                self.stateImg = 'SensorOff'

        if self.onState: self.expired = False
        if self.count:   self.reset   = False

        self.displayState = self.state
        if self.plugin.showTimer:
            if self.state in ['active','persist']:
                self.displayState = format_seconds(self.offTime   - self.taskTime)
            elif self.state == 'accrue':
                self.displayState = format_seconds(self.resetTime - self.taskTime)

################################################################################
class ThresholdTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(ThresholdTimer, self).__init__(instance, plugin)

        self.threshold  = int(instance.pluginProps.get('countThreshold',1))
        self.resetDelta = self.delta( instance.pluginProps.get('resetCycles',1),
                                      instance.pluginProps.get('resetUnits','minutes') )
        self.offDelta   = self.delta( instance.pluginProps.get('offCycles', 10),
                                      instance.pluginProps.get('offUnits',  'minutes') )

        self.trackCount = len(self.deviceStateDict) + len(self.variableList)

        # initial state
        self.count = 0
        for devId, stateId in self.deviceStateDict.items():
            if self.getBoolValue(indigo.devices[devId].states[stateId]):
                self.count += 1
        for varId in self.variableList:
            if self.getBoolValue(indigo.variables[varId].value):
                self.count += 1
        if (self.count >= self.threshold) or (self.taskTime < self.offTime):
            self.onState = True
        self.update()

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _offTimeGet(self):
        return self.states['offTime']
    def _offTimeSet(self, value):
        self.states['offTime'] = value
        self.states['offString'] = format_datetime(value)
    offTime = property(_offTimeGet, _offTimeSet)

    def _countGet(self):
        return self.states['count']
    def _countSet(self, value):
        self.states['count'] = value
        self.states['counting'] = bool(value)
    count = property(_countGet, _countSet)

    def _expiredGet(self):
        return self.states['expired']
    def _expiredSet(self, value):
        self.states['expired'] = value
    expired = property(_expiredGet, _expiredSet)

    def _resetTimeGet(self):
        return self.states['resetTime']
    def _resetTimeSet(self, value):
        self.states['resetTime'] = value
        self.states['resetString'] = format_datetime(value)
    resetTime = property(_resetTimeGet, _resetTimeSet)

    #-------------------------------------------------------------------------------
    def tick(self):
        if (self.state == 'persist') and (self.taskTime >= self.offTime):
            self.onState = False
            self.expired = True
            self.logger.debug('"{}" timer:{} [onOff:{}, count:{}, expired:{}]'
                .format(self.name, 'offTime', self.onState, self.count, self.expired))
        self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        if newVal:
            self.count += 1
            if self.count > self.trackCount:
                self.logger.error('"{}" count out of sync [count:{}, max:{}]'
                    .format(self.name, self.count, self.trackCount))
                self.count = self.trackCount
            if self.count >= self.threshold:
                self.onState = True
        else:
            self.count -= 1
            if self.count < 0:
                self.logger.error('"{}" count out of sync [count:{}, max:{}]'
                    .format(self.name, self.count, self.trackCount))
                self.count = 0
            if (self.state == 'active') and (self.count < self.threshold):
                self.offTime = self.taskTime + self.offDelta
        self.logger.debug('"{}" input:{} [onOff:{}, count:{}, expired:{}]'
            .format(self.name, newVal, self.onState, self.count, self.expired))
        self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.onState = True
        self.offTime = self.taskTime + self.offDelta
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        if self.count:
            self.count = 0
        if self.onState:
            self.onState = False
            self.offTime = self.taskTime
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.onState:
            if (self.count >= self.threshold):
                self.state = 'active'
                self.stateImg = 'SensorOn'
            else:
                self.state = 'persist'
                self.stateImg = 'TimerOn'
        else:
            if self.count:
                self.state = 'accrue'
                self.stateImg = 'TimerOff'
            else:
                self.state = 'idle'
                self.stateImg = 'SensorOff'

        if self.onState: self.expired = False

        self.displayState = self.state
        if self.plugin.showTimer:
            if self.state == 'persist':
                self.displayState = format_seconds(self.offTime   - self.taskTime)

################################################################################
class PersistenceTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(PersistenceTimer, self).__init__(instance, plugin)

        self.onDelta  = self.delta( instance.pluginProps.get('onCycles',30),
                                    instance.pluginProps.get('onUnits','seconds') )
        self.offDelta = self.delta( instance.pluginProps.get('offCycles',30),
                                    instance.pluginProps.get('offUnits','seconds') )

        # initial state
        self.tick()
        if instance.pluginProps['trackEntity'] == 'dev':
            devId, state = self.deviceStateDict.items()[0]
            self.tock(self.getBoolValue(indigo.devices[devId].states[state]))
            self.variableList = list()
        else:
            self.tock(self.getBoolValue(indigo.variables[self.variableList[0]].value))
            self.deviceStateDict = dict()

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _offTimeGet(self):
        return self.states['offTime']
    def _offTimeSet(self, value):
        self.states['offTime'] = value
        self.states['offString'] = format_datetime(value)
    offTime = property(_offTimeGet, _offTimeSet)

    def _pendingGet(self):
        return self.states['pending']
    def _pendingSet(self, value):
        self.states['pending'] = value
    pending = property(_pendingGet, _pendingSet)

    def _onTimeGet(self):
        return self.states['onTime']
    def _onTimeSet(self, value):
        self.states['onTime'] = value
        self.states['onString'] = format_datetime(value)
    onTime = property(_onTimeGet, _onTimeSet)

    #-------------------------------------------------------------------------------
    def tick(self):
        if self.pending:
            if  self.onState and self.taskTime >= self.offTime:
                self.pending = False
                self.onState = False
                logTimer = 'offTime'
            elif not self.onState and self.taskTime >= self.onTime:
                self.pending = False
                self.onState = True
                logTimer = 'onTime'
            if not self.pending:
                self.logger.debug('"{}" timer:{} [onOff:{}, pending:{}]'
                    .format(self.name, logTimer, self.onState, self.pending))
            self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        if newVal == self.onState:
            self.pending = False
        else:
            if self.onState:
                if self.offDelta:
                    self.pending = True
                    self.offTime = self.taskTime + self.offDelta
                else:
                    self.onState = False
                    self.offTime = self.taskTime
            else:
                if self.onDelta:
                    self.pending = True
                    self.onTime = self.taskTime + self.onDelta
                else:
                    self.onState = True
                    self.onTime = self.taskTime
        self.logger.debug('"{}" input:{} [onOff:{}, pending:{}]'
            .format(self.name, newVal, self.onState, self.pending))
        self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.onState = True
        self.pending = False
        self.onTime = self.taskTime
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        self.onState = False
        self.pending = False
        self.offTime = self.taskTime
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.onState:
            if self.pending:
                self.state = 'pending'
                self.stateImg = 'TimerOn'
            else:
                self.state = 'on'
                self.stateImg = 'SensorOn'
        else:
            if self.pending:
                self.state = 'pending'
                self.stateImg = 'TimerOff'
            else:
                self.state = 'off'
                self.stateImg = 'SensorOff'

        if self.plugin.showTimer and self.pending:
            if self.onState:
                self.displayState = format_seconds(self.offTime - self.taskTime)
            else:
                self.displayState = format_seconds(self.onTime - self.taskTime)
        else:
            self.displayState = self.state

################################################################################
class LockoutTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(LockoutTimer, self).__init__(instance, plugin)

        self.onDelta  = self.delta( instance.pluginProps.get('onCycles',30),
                                    instance.pluginProps.get('onUnits','seconds') )
        self.offDelta = self.delta( instance.pluginProps.get('offCycles',30),
                                    instance.pluginProps.get('offUnits','seconds') )

        # initial state
        self.lastVal = self.onState
        self.tick()
        if instance.pluginProps['trackEntity'] == 'dev':
            devId, state = self.deviceStateDict.items()[0]
            self.tock(self.getBoolValue(indigo.devices[devId].states[state]))
            self.variableList = list()
        else:
            self.tock(self.getBoolValue(indigo.variables[self.variableList[0]].value))
            self.deviceStateDict = dict()

    #-------------------------------------------------------------------------------
    # properties
    #-------------------------------------------------------------------------------
    def _offTimeGet(self):
        return self.states['offTime']
    def _offTimeSet(self, value):
        self.states['offTime'] = value
        self.states['offString'] = format_datetime(value)
    offTime = property(_offTimeGet, _offTimeSet)

    def _lockedGet(self):
        return self.states['locked']
    def _lockedSet(self, value):
        self.states['locked'] = value
    locked = property(_lockedGet, _lockedSet)

    def _onTimeGet(self):
        return self.states['onTime']
    def _onTimeSet(self, value):
        self.states['onTime'] = value
        self.states['onString'] = format_datetime(value)
    onTime = property(_onTimeGet, _onTimeSet)

    #-------------------------------------------------------------------------------
    def tick(self):
        if self.locked:
            if  self.onState and self.taskTime >= self.onTime:
                self.locked = False
                logTimer = 'onTime'
            elif not self.onState and self.taskTime >= self.offTime:
                self.locked = False
                logTimer = 'offTime'
            if not self.locked:
                self.logger.debug('"{}" timer:{} [onOff:{}, locked:{}]'
                    .format(self.name, logTimer, self.onState, self.locked))
            self.update()
            if not self.locked:
                self.doTask('tock', self.lastVal)

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        self.lastVal = newVal
        if not self.locked:
            if newVal != self.onState:
                self.onState = newVal
                self.locked = True
                if newVal:
                    self.onTime  = self.taskTime + self.onDelta
                else:
                    self.offTime = self.taskTime + self.offDelta
        self.logger.debug('"{}" input:{} [onOff:{}, locked:{}]'
            .format(self.name, newVal, self.onState, self.locked))
        self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.onState = True
        self.locked = True
        self.onTime  = self.taskTime + self.onDelta
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        self.onState = False
        self.locked = True
        self.offTime = self.taskTime + self.offDelta
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.onState:
            if self.locked:
                self.state = 'locked'
                self.stateImg = 'TimerOn'
            else:
                self.state = 'on'
                self.stateImg = 'SensorOn'
        else:
            if self.locked:
                self.state = 'locked'
                self.stateImg = 'TimerOff'
            else:
                self.state = 'off'
                self.stateImg = 'SensorOff'

        if self.plugin.showTimer and self.locked:
            if self.onState:
                self.displayState = format_seconds(self.onTime - self.taskTime)
            else:
                self.displayState = format_seconds(self.offTime - self.taskTime)
        else:
            self.displayState = self.state

################################################################################
class AliveTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(AliveTimer, self).__init__(instance, plugin)

        self.offDelta = self.delta( instance.pluginProps.get('offCycles',30),
                                    instance.pluginProps.get('offUnits','seconds') )

        # initial state
        if instance.pluginProps['trackEntity'] == 'dev':
            devId, state = self.deviceStateDict.items()[0]
            lastDateTime = indigo.devices[devId].lastChanged
            lastTimeTime = time.mktime(lastDateTime.timetuple())
            self.offTime = lastTimeTime + self.offDelta
            self.onState = (time.time() < self.offTime)
            self.variableList = list()
        else:
            # no last changed data available for variables
            # onState initialized to whatever it was before
            self.deviceStateDict = dict()
        self.tick()

    #-------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------
    def _offTimeGet(self):
        return self.states['offTime']
    def _offTimeSet(self, value):
        self.states['offTime'] = value
        self.states['offString'] = format_datetime(value)
    offTime = property(_offTimeGet, _offTimeSet)

    #-------------------------------------------------------------------------------
    def tick(self):
        if self.onState and self.taskTime >= self.offTime:
            self.onState = False
            self.logger.debug('"{}" timer:{} [onOff:{}]'
                .format(self.name, "offTimer", self.onState))
        self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        self.onState = True
        self.offTime = self.taskTime + self.offDelta
        self.logger.debug('"{}" input:{} [onOff:{}]'
            .format(self.name, newVal, self.onState))
        self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.onState = True
        self.offTime = self.taskTime + self.offDelta
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        self.onState = False
        self.offTime = self.taskTime
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.onState:
            self.state = 'on'
            self.stateImg = 'TimerOn'
        else:
            self.state = 'off'
            self.stateImg = 'SensorOff'

        if self.plugin.showTimer and self.onState:
            self.displayState = format_seconds(self.offTime - self.taskTime)
        else:
            self.displayState = self.state

    #-------------------------------------------------------------------------------
    # override base class methods
    #-------------------------------------------------------------------------------
    def devChanged(self, oldDev, newDev):
        if newDev.id in self.deviceStateDict:
            if self.plugin.verbose:
                self.logger.debug('"{}" devChanged:"{}"'.format(self.name, newDev.name))
            self.tock(True)

    #-------------------------------------------------------------------------------
    def varChanged(self, oldVar, newVar):
        if newVar.id in self.variableList:
            if self.plugin.verbose:
                self.logger.debug('"{}" varChanged:"{}"'.format(self.name, newVar.name))
            self.tock(True)

################################################################################
class RunningTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(RunningTimer, self).__init__(instance, plugin)

        self.updateDelta = int(instance.pluginProps.get('updateSeconds',60))
        self.updateTime  = 0

        if instance.pluginProps['trackEntity'] == 'dev':
            devId, state = self.deviceStateDict.items()[0]
            dev = indigo.devices[devId]
            lastDateTime = dev.lastChanged
            lastTimeTime = time.mktime(lastDateTime.timetuple())
            self.onState = self.getBoolValue(dev.states[state])
            if self.onState:
                self.onTime = max(self.onTime,lastTimeTime)
            self.variableList = list()
        else:
            self.onState = self.getBoolValue(indigo.variables[self.variableList[0]].value)
            self.deviceStateDict = dict()


        # INITIALIZE TIMESPAN DICTIONARIES
        # task_spans: numerical timespans of current task
        self.task_spans = dict()
        self.updateTaskSpans()

        # save_spans: numerical timespans last saved to device
        try:
            self.save_spans = literal_eval(self.states['zzzSaveSpanDict'])
        except:
            self.save_spans = dict()
        for span in k_timeSpans:
            if not self.save_spans.get(span,None): self.save_spans[span] = self.task_spans[span]

        # start_spans: epoch time for the start of current timespans
        year  = self.save_spans['y']
        month = self.save_spans['m']
        day   = self.save_spans['d']
        hour  = self.save_spans['h']
        self.start_spans = {
            'h': time.mktime(datetime(year, month, day, hour).timetuple()),
            'd': time.mktime(datetime(year, month, day).timetuple()),
            'm': time.mktime(datetime(year, month, 1).timetuple()),
            'y': time.mktime(datetime(year, 1, 1).timetuple()),
            'c': self.onTime,
            }
        self.start_spans['w'] = self.start_spans['d'] - (time.localtime(self.start_spans['d']).tm_wday*24*60*60)

        # done_spans: accumulated seconds for each current timespan already saved to device's states
        try:
            self.done_spans = literal_eval(self.states['zzzSecsDoneDict'])
        except:
            self.done_spans = dict()
        for span in k_timeSpans:
            if not self.done_spans.get(span,None): self.done_spans[span] = 0

        # running_spans: total accumulated seconds for each current and prior timespan
        self.running_spans = dict()
        for span, name in k_timeSpans.items():
            self.running_spans[span] = {i:self.states['seconds{}{:0>2d}'.format(name,i)] for i in range(k_periodRange[span])}
        self.updateRunningSpans()


        # INITALIZE DEVICE STATES
        for span in k_timeSpans:
            if self.task_spans[span] != self.save_spans[span]:
                # we are now in a new time span
                # estimate inital accumulated seconds for new span
                if self.onState:
                    self.done_spans[span] = self.taskTime - self.start_spans[span]
                else:
                    self.done_spans[span] = 0
                # set the accumulated seconds for the prior spans
                self.rolloverSpan(span)
                # start timer for new span now
                self.start_spans[span] = self.taskTime
                # save new span so we know when it changes again
                self.save_spans[span] = self.task_spans[span]

        if not self.onState and self.running_spans['c'][0]:
            self.rolloverSpan('c')

        self.saveSpanStates()

    #-------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------
    def _offTimeGet(self):
        return self.states['offTime']
    def _offTimeSet(self, value):
        self.states['offTime'] = value
        self.states['offString'] = format_datetime(value)
    offTime = property(_offTimeGet, _offTimeSet)

    def _onTimeGet(self):
        return self.states['onTime']
    def _onTimeSet(self, value):
        self.states['onTime'] = value
        self.states['onString'] = format_datetime(value)
    onTime = property(_onTimeGet, _onTimeSet)

    #-------------------------------------------------------------------------------
    def tick(self):
        # update current hour, day, week, month, year
        self.updateTaskSpans()
        # updated accumulated time for each span
        self.updateRunningSpans()

        logTimer = None

        if  self.updateDelta and self.onState and self.taskTime >= self.updateTime:
            self.updateTime = self.taskTime + self.updateDelta
            logTimer = 'updateTime'

        for span in k_timeSpans:
            if self.task_spans[span] != self.save_spans[span]:
                # we are now in a new time span
                if self.plugin.verbose:
                    self.logger.debug('new span "{}": {} -> {}'.format(span, self.saved.spans[span],self.task.spans[span]))
                # set the accumulated seconds for the prior spans
                self.rolloverSpan(span)
                # set inital accumulated seconds for new span to zero
                self.done_spans[span] = 0
                # start timer for new span now
                self.start_spans[span] = self.taskTime
                # save new span so we know when it changes again
                self.save_spans[span] = self.task_spans[span]
                # update states when done
                logTimer = 'newSpan({})'.format(span)

        if logTimer:
            self.logger.debug('"{}" timer:{} [onOff:{}, onSec:{}, update:{}]'
                .format(self.name, logTimer, self.onState, self.running_spans['c'][0], self.updateTime))
            self.saveSpanStates()
        elif self.plugin.showTimer:
            self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        # update current hour, day, week, month, year
        self.updateTaskSpans()
        # updated accumulated time for each span
        self.updateRunningSpans()

        if newVal:
            # set device state to on
            self.onState = True
            # record time device went on
            self.onTime = self.taskTime
        else:
            for span in k_timeSpans:
                # save accumulated timer value
                self.done_spans[span] = self.running_spans[span][0]

            self.rolloverSpan('c')

            # set device state to off
            self.onState = False
            # record time device went off
            self.offTime = self.taskTime

        self.logger.debug('"{}" input:{} [onOff:{}]'
            .format(self.name, newVal, self.onState))
        self.saveSpanStates()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.tock(True)

    #-------------------------------------------------------------------------------
    def turnOff(self):
        self.tock(False)

    #-------------------------------------------------------------------------------
    def updateTaskSpans(self):
        dt = datetime.fromtimestamp(self.taskTime)
        self.task_spans = {
            'h': dt.hour,
            'd': dt.day,
            'w': dt.isocalendar()[1],
            'm': dt.month,
            'y': dt.year,
            'c': 0
        }

    #-------------------------------------------------------------------------------
    def updateRunningSpans(self):
        for span in k_timeSpans:
            if self.onState:
                accumulated = self.taskTime - max(self.onTime, self.start_spans[span])
            else:
                accumulated = 0
            if span =='c':
                self.running_spans[span][0] = accumulated
            else:
                self.running_spans[span][0] = self.done_spans[span] + accumulated

    #-------------------------------------------------------------------------------
    def rolloverSpan(self, span):
        for i in range(k_periodRange[span]-1,0,-1):
            self.running_spans[span][i] = self.running_spans[span][i-1]
        self.running_spans[span][0] = 0

    #-------------------------------------------------------------------------------
    def saveSpanStates(self):
        #save_spans
        self.states['zzzSaveSpanDict'] = repr(self.save_spans)
        #done_spans
        self.states['zzzSecsDoneDict'] = repr(self.done_spans)
        # running_spans
        for span, name in k_timeSpans.items():
            for i in range(k_periodRange[span]):
                self.states['seconds{}{:0>2d}'.format(name,i)] = int(round(self.running_spans[span][i]))
                self.states['string{}{:0>2d}'.format(name,i)] = format_seconds(self.running_spans[span][i])

            # FIXME depricated state names
            # remove after respectful transition period
            self.states['secondsThis{}'.format(name)] = int(round(self.running_spans[span][0]))
            self.states['stringThis{}'.format(name)]  = format_seconds(self.running_spans[span][0])
            self.states['secondsLast{}'.format(name)] = int(round(self.running_spans[span][1]))
            self.states['stringLast{}'.format(name)]  = format_seconds(self.running_spans[span][1])
            # /FIXME

        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.onState:
            self.state = 'on'
            self.stateImg = 'TimerOn'
        else:
            self.state = 'off'
            self.stateImg = 'SensorOff'

        if self.plugin.showTimer and self.onState:
            self.displayState = format_seconds(self.taskTime - self.onTime)
        else:
            self.displayState = self.state

################################################################################
# Utilities
################################################################################

def zint(value):
    try: return int(value)
    except: return 0

#-------------------------------------------------------------------------------
def ver(vstr): return tuple(map(int, (vstr.split('.'))))

#-------------------------------------------------------------------------------
def format_datetime(t=None):
    if not t: t = time.time()
    return time.strftime(k_strftimeFormat,time.localtime(t))

#-------------------------------------------------------------------------------
def format_seconds(value):
    days, remainder  = divmod(int(round(value)),86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return '{}-{:0>2d}:{:0>2d}:{:0>2d}'.format(days, hours, minutes, seconds)
    else:
        return '{}:{:0>2d}:{:0>2d}'.format(hours, minutes, seconds)
