#! /usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# http://www.indigodomo.com

import indigo
import threading
import Queue
import time
from ghpu import GitHubPluginUpdater

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
    )

k_variableKeys = (
    'variable1',
    'variable2',
    'variable3',
    'variable4',
    'variable5',
    )

k_tickSeconds = 1

kPluginUpdateCheckHours = 24

k_strftimeFormat = '%Y-%m-%d %H:%M:%S'

################################################################################
class Plugin(indigo.PluginBase):
    #-------------------------------------------------------------------------------
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.updater = GitHubPluginUpdater(self)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.nextCheck      = self.pluginPrefs.get('nextUpdateCheck',0)
        self.showTimer      = self.pluginPrefs.get('showTimer',False)
        self.debug          = self.pluginPrefs.get('showDebugInfo',False)
        self.verbose        = self.pluginPrefs.get('verboseDebug',False)
        self.logger.debug("startup")
        if self.debug:
            self.logger.debug("Debug logging enabled")

        self.deviceDict     = dict()
        self.tickTime       = time.time()

        indigo.devices.subscribeToChanges()
        indigo.variables.subscribeToChanges()

    #-------------------------------------------------------------------------------
    def shutdown(self):
        self.logger.debug("shutdown")
        self.pluginPrefs['showDebugInfo'] = self.debug
        self.pluginPrefs['verboseDebug'] = self.verbose
        self.pluginPrefs['showTimer'] = self.showTimer
        self.pluginPrefs['nextUpdateCheck'] = self.nextCheck

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
            self.verbose   = valuesDict.get('verboseDebug',False)
            self.showTimer = valuesDict.get('showTimer',True)
            if self.debug:
                self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    def runConcurrentThread(self):
        try:
            while True:
                self.tickTime = time.time()
                for devId, device in self.deviceDict.iteritems():
                    device.doTask('tick')
                if self.tickTime > self.nextCheck:
                    self.checkForUpdates()
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
            elif dev.deviceTypeId == 'persistenceTimer':
                self.deviceDict[dev.id] = PersistenceTimer(dev, self)
            elif dev.deviceTypeId == 'lockoutTimer':
                self.deviceDict[dev.id] = LockoutTimer(dev, self)
            # start the thread
            self.deviceDict[dev.id].start()

    #-------------------------------------------------------------------------------
    def deviceStopComm(self, dev):
        if dev.id in self.deviceDict:
            self.deviceDict[dev.id].cancel()
            del self.deviceDict[dev.id]

    #-------------------------------------------------------------------------------
    def validateDeviceConfigUi(self, valuesDict, typeId, devId, runtime=False):
        self.logger.debug("validateDeviceConfigUi: " + typeId)
        errorsDict = indigo.Dict()

        if typeId == 'activityTimer':
            for devKey, stateKey in k_deviceKeys:
                if zint(valuesDict.get(devKey,'')) and not valuesDict.get(stateKey,''):
                    errorsDict[stateKey] = "Required"
            requiredIntegers = ['resetCycles','countThreshold','offCycles']

        elif typeId in ['persistenceTimer','lockoutTimer']:
            requiredIntegers = ['onCycles','offCycles']
            if valuesDict.get('trackEntity','dev') == 'dev':
                keys = k_deviceKeys[0]
            else:
                keys = [k_variableKeys[0]]
            for key in keys:
                if not valuesDict.get(key,''):
                    errorsDict[key] = "Required"

        for key in requiredIntegers:
            if not valuesDict.get(key,"").isdigit():
                errorsDict[key] = "Must be an integer zero or greater"

        if valuesDict.get('logicType','simple') == 'complex':
            if valuesDict.get('valueType','str') == 'num':
                try:
                    temp = float(valuesDict.get('value',''))
                except:
                    errorsDict['value'] = "Make value a number or change data type"

        if len(errorsDict) > 0:
            self.logger.debug('validate device config error: \n{}'.format(errorsDict))
            return (False, valuesDict, errorsDict)
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

        # push to server
        theProps["version"] = self.pluginVersion
        dev.replacePluginPropsOnServer(theProps)

    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):

        # device belongs to plugin
        if newDev.pluginId == self.pluginId or oldDev.pluginId == self.pluginId:
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)

        else:
            for devId, device in self.deviceDict.items():
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
            self.logger.error('device id "%s" not available' % action.deviceId)

    #-------------------------------------------------------------------------------
    def forceOff(self, action):
        self.logger.debug(str(action))
        if action.deviceId in self.deviceDict:
            self.deviceDict[action.deviceId].doTask('turnOff')
        else:
            self.logger.error('device id "%s" not available' % action.deviceId)

    #-------------------------------------------------------------------------------
    # Menu Methods
    #-------------------------------------------------------------------------------
    def checkForUpdates(self):
        self.nextCheck = time.time() + (kPluginUpdateCheckHours*60*60)
        try:
            self.updater.checkForUpdate()
        except Exception as e:
            msg = 'Check for update error.  Next attempt in {} hours.'.format(kPluginUpdateCheckHours)
            if self.debug:
                self.logger.exception(msg)
            else:
                self.logger.error(msg)
                self.logger.debug(e)

    #-------------------------------------------------------------------------------
    def updatePlugin(self):
        self.updater.update()

    #-------------------------------------------------------------------------------
    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

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
        devList = list()
        excludeList  = [dev.id for dev in indigo.devices.iter(filter='self')]
        for dev in indigo.devices.iter():
            if not dev.id in excludeList:
                devList.append((dev.id, dev.name))
        devList.append((0,"- none -"))
        return devList

    #-------------------------------------------------------------------------------
    def getStateList(self, filter=None, valuesDict=dict(), typeId='', targetId=0):
        stateList = list()
        devId = zint(valuesDict.get(filter,''))
        if devId:
            for state in indigo.devices[devId].states:
                stateList.append((state,state))
        return stateList

    #-------------------------------------------------------------------------------
    def getVariableList(self, filter='', valuesDict=dict(), typeId='', targetId=0):
        varList = list()
        for var in indigo.variables.iter():
            varList.append((var.id, var.name))
        varList.append((0,"- none -"))
        return varList

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

    #-------------------------------------------------------------------------------
    def run(self):
        self.logger.debug('"{}" thread started'.format(self.name))
        while not self.cancelled:
            try:
                task,arg1,arg2 = self.queue.get(True,2)
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
                else:
                    self.logger.error('"{}" task "{}" not recognized'.format(self.name,task))
                self.queue.task_done()
            except Queue.Empty:
                pass
            except Exception as e:
                self.logger.error('"{}" thread error \n{}'.format(self.name, e))
        else:
            self.logger.debug('"{}" thread cancelled'.format(self.name))

    #-------------------------------------------------------------------------------
    def cancel(self):
        """End this thread"""
        self.cancelled = True

    #-------------------------------------------------------------------------------
    def doTask(self, task, arg1=None, arg2=None):
        self.queue.put((task, arg1, arg2))

    #-------------------------------------------------------------------------------
    def devChanged(self, oldDev, newDev):
        if newDev.id in self.deviceStateDict:
            stateKey = self.deviceStateDict[newDev.id]
            if oldDev.states[stateKey] != newDev.states[stateKey]:
                self.tock(self.getBoolValue(newDev.states[stateKey]))

    #-------------------------------------------------------------------------------
    def varChanged(self, oldVar, newVar):
        if newVar.id in self.variableList:
            if oldVar.value != newVar.value:
                self.tock(self.getBoolValue(newVar.value))

    #-------------------------------------------------------------------------------
    def update(self, force=False):
        if force or self.plugin.showTimer or (self.states != self.dev.states):

            self.getStates()

            newStates = list()
            for key, value in self.states.iteritems():
                if self.states[key] != self.dev.states[key]:
                    newStates.append({'key':key,'value':value})
                    if key == 'onOffState' and self.logOnOff:
                        self.logger.info('"{0}" {1}'.format(self.name, ['off','on'][value]))
                    elif key == 'state':
                        self.dev.updateStateImageOnServer(k_stateImages[self.stateImg])

            if len(newStates) > 0:
                if self.plugin.verbose:
                    logStates = ""
                    for item in newStates:
                        logStates += '{}:{}, '.format(item['key'],item['value'])
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
    def countdown(self, value):
        hours, remainder = divmod(zint(value), 3600)
        minutes, seconds = divmod(remainder, 60)
        return '{}:{:0>2d}:{:0>2d}'.format(hours, minutes, seconds)

    #-------------------------------------------------------------------------------
    def timestamp(self, t=None):
        if not t: t = time.time()
        return time.strftime(k_strftimeFormat,time.localtime(t))

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
        self.resetDelta = self.delta(instance.pluginProps.get('resetCycles',1), instance.pluginProps.get('resetUnits','minutes'))
        self.offDelta   = self.delta(instance.pluginProps.get('offCycles', 10), instance.pluginProps.get('offUnits',  'minutes'))

        # initial state
        self.states['onOffState'] = False
        self.states['reset'] = False
        self.states['expired'] = False
        self.states['count'] = 0
        self.update(True)

    #-------------------------------------------------------------------------------
    def tick(self):
        reset = expired = False
        if self.states['count'] and (self.taskTime >= self.states['resetTime']):
            self.states['count'] = 0
            self.states['reset'] = True
        if self.states['onOffState'] and (self.taskTime >= self.states['offTime']):
            self.states['onOffState'] = False
            self.states['expired'] = True
        self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        self.logger.debug('"{}" input:  [newVal:{}, onOff:{}, count:{}]'.format(self.name, newVal, self.states['onOffState'], self.states['count']))
        if newVal:
            self.states['count'] += 1
            self.states['resetTime'] = self.taskTime + self.resetDelta
            if self.states['count'] >= self.threshold:
                self.states['onOffState'] = True
                self.states['offTime'] = self.taskTime + self.offDelta
            elif self.states['onOffState'] and self.extend:
                self.states['offTime'] = self.taskTime + self.offDelta
            self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.states['onOffState'] = True
        self.states['offTime'] = self.taskTime + self.offDelta
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        if self.states['count']:
            self.states['count'] = 0
            self.states['resetTime'] = self.taskTime
        if self.states['onOffState']:
            self.states['onOffState'] = False
            self.states['offTime'] = self.taskTime
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.states['onOffState']:
            if (self.states['count'] >= self.threshold) or (self.states['count'] and self.extend):
                self.states['state'] = 'active'
                self.stateImg = 'TimerOn'
            else:
                self.states['state'] = 'persist'
                self.stateImg = 'SensorOn'
        else:
            if self.states['count']:
                self.states['state'] = 'accrue'
                self.stateImg = 'TimerOff'
            else:
                self.states['state'] = 'idle'
                self.stateImg = 'SensorOff'

        self.states['resetString']   = self.timestamp(self.states['resetTime'])
        self.states['offString']     = self.timestamp(self.states['offTime'])
        self.states['counting']      = bool(self.states['count'])
        if self.states['onOffState']:  self.states['expired'] = False
        if self.states['counting']:    self.states['reset']   = False

        self.states['displayState'] = self.states['state']
        if self.plugin.showTimer:
            if self.states['state'] in ['active','persist']:
                self.states['displayState'] = self.countdown(self.states['offTime']   - self.taskTime)
            elif self.states['state'] == 'accrue':
                self.states['displayState'] = self.countdown(self.states['resetTime'] - self.taskTime)

################################################################################
class PersistenceTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(PersistenceTimer, self).__init__(instance, plugin)

        self.onDelta  = self.delta(instance.pluginProps.get('onCycles',30), instance.pluginProps.get('onUnits','seconds'))
        self.offDelta = self.delta(instance.pluginProps.get('offCycles',30), instance.pluginProps.get('offUnits','seconds'))

        # initial state
        self.states['pending'] = False
        if instance.pluginProps['trackEntity'] == 'dev':
            devId, state = self.deviceStateDict.items()[0]
            self.states['onOffState'] = self.getBoolValue(indigo.devices[devId].states[state])
        else:
            self.states['onOffState'] = self.getBoolValue(indigo.variables[self.variableList[0]].value)
        self.update(True)

    #-------------------------------------------------------------------------------
    def tick(self):
        if self.states['pending']:
            if  self.states['onOffState'] and self.taskTime >= self.states['offTime']:
                self.states['pending'] = False
                self.states['onOffState'] = False
            elif not self.states['onOffState'] and self.taskTime >= self.states['onTime']:
                self.states['pending'] = False
                self.states['onOffState'] = True
            self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        self.logger.debug('"{}" input:  [newVal:{}, onOff:{}, pending:{}]'.format(self.name, newVal, self.states['onOffState'], self.states['pending']))
        if newVal == self.states['onOffState']:
            self.states['pending'] = False
        else:
            if self.states['onOffState']:
                if self.offDelta:
                    self.states['pending'] = True
                    self.states['offTime'] = self.taskTime + self.offDelta
                else:
                    self.states['onOffState'] = False
            else:
                if self.onDelta:
                    self.states['pending'] = True
                    self.states['onTime'] = self.taskTime + self.onDelta
                else:
                    self.states['onOffState'] = True
        self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.states['onOffState'] = True
        self.states['pending'] = False
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        self.states['onOffState'] = False
        self.states['pending'] = False
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.states['onOffState']:
            if self.states['pending']:
                self.states['state'] = 'pending'
                self.stateImg = 'TimerOn'
            else:
                self.states['state'] = 'on'
                self.stateImg = 'SensorOn'
        else:
            if self.states['pending']:
                self.states['state'] = 'pending'
                self.stateImg = 'TimerOff'
            else:
                self.states['state'] = 'off'
                self.stateImg = 'SensorOff'

        self.states['onString']   = self.timestamp(self.states['onTime'])
        self.states['offString']  = self.timestamp(self.states['offTime'])

        if self.plugin.showTimer and self.states['pending']:
            if self.states['onOffState']:
                self.states['displayState'] = self.countdown(self.states['offTime'] - self.taskTime)
            else:
                self.states['displayState'] = self.countdown(self.states['onTime'] - self.taskTime)
        else:
            self.states['displayState'] = self.states['state']

################################################################################
class LockoutTimer(TimerBase):

    #-------------------------------------------------------------------------------
    def __init__(self, instance, plugin):
        super(LockoutTimer, self).__init__(instance, plugin)

        self.onDelta  = self.delta(instance.pluginProps.get('onCycles',30), instance.pluginProps.get('onUnits','seconds'))
        self.offDelta = self.delta(instance.pluginProps.get('offCycles',30), instance.pluginProps.get('offUnits','seconds'))

        # initial state
        self.states['locked'] = False
        if instance.pluginProps['trackEntity'] == 'dev':
            devId, state = self.deviceStateDict.items()[0]
            self.lastVal = self.getBoolValue(indigo.devices[devId].states[state])
        else:
            self.lastVal = self.getBoolValue(indigo.variables[self.variableList[0]].value)
        self.states['onOffState'] = self.lastVal
        self.update(True)

    #-------------------------------------------------------------------------------
    def tick(self):
        if self.states['locked']:
            if  (    self.states['onOffState'] and self.taskTime >= self.states['onTime'] ) or \
                (not self.states['onOffState'] and self.taskTime >= self.states['offTime']):
                self.states['locked'] = False
                self.doTask('tock',self.lastVal)
            self.update()

    #-------------------------------------------------------------------------------
    def tock(self, newVal):
        self.logger.debug('"{}" input:  [newVal:{}, onOff:{}, locked:{}]'.format(self.name, newVal, self.states['onOffState'], self.states['locked']))
        self.lastVal = newVal
        if not self.states['locked']:
            if newVal != self.states['onOffState']:
                self.states['onOffState'] = newVal
                self.states['locked'] = True
                if newVal:
                    self.states['onTime']  = self.taskTime + self.onDelta
                else:
                    self.states['offTime'] = self.taskTime + self.offDelta
                self.update()

    #-------------------------------------------------------------------------------
    def turnOn(self):
        self.states['onOffState'] = True
        self.states['locked'] = False
        self.update()

    #-------------------------------------------------------------------------------
    def turnOff(self):
        self.states['onOffState'] = False
        self.states['locked'] = False
        self.update()

    #-------------------------------------------------------------------------------
    def getStates(self):
        if self.states['onOffState']:
            if self.states['locked']:
                self.states['state'] = 'locked'
                self.stateImg = 'TimerOn'
            else:
                self.states['state'] = 'on'
                self.stateImg = 'SensorOn'
        else:
            if self.states['locked']:
                self.states['state'] = 'locked'
                self.stateImg = 'TimerOff'
            else:
                self.states['state'] = 'off'
                self.stateImg = 'SensorOff'

        self.states['onString']   = self.timestamp(self.states['onTime'])
        self.states['offString']  = self.timestamp(self.states['offTime'])

        if self.plugin.showTimer and self.states['locked']:
            if self.states['onOffState']:
                self.states['displayState'] = self.countdown(self.states['onTime'] - self.taskTime)
            else:
                self.states['displayState'] = self.countdown(self.states['offTime'] - self.taskTime)
        else:
            self.states['displayState'] = self.states['state']

################################################################################
# Utilities
################################################################################

def zint(value):
    try: return int(value)
    except: return 0

#-------------------------------------------------------------------------------
def ver(vstr): return tuple(map(int, (vstr.split('.'))))
