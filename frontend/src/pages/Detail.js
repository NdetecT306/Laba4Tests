// backend/frontend/src/pages/Detail.js
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function Detail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { api } = useAuth();
  const [chps, setChps] = useState([]);
  const [houses, setHouses] = useState([]);
  const [entity, setEntity] = useState(null);
  const [entityType, setEntityType] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState(null);
  const [chpStatus, setChpStatus] = useState({});

  const checkChpStatus = useCallback((chpId, currentHouses) => {
    const chpHouses = currentHouses.filter(house => house.chpId === chpId);
    if (chpHouses.length === 0) {
      return 'working';
    }
    const allAtMax = chpHouses.every(house => house.temperature === 95);
    const allAtMin = chpHouses.every(house => house.temperature === 40);
    if (allAtMax || allAtMin) {
      return 'off';
    }
    return 'working';
  }, []);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [chpsRes, housesRes] = await Promise.all([
        api.get('/chps'),
        api.get('/houses')
      ]);
      
      const chpsData = chpsRes.data.map(chp => ({
        id: chp.ID,
        name: chp.Название,
        capacity: chp.Мощность,
        location: chp.Расположение,
        x: chp.Координата_X,
        y: chp.Координата_Y
      }));
      
      const housesData = housesRes.data.map(house => ({
        id: house.ID,
        name: house.Название,
        type: house.Тип,
        chpId: house.ID_ТЭЦ,
        temperature: house.Температура,
        x: house.Координата_X,
        y: house.Координата_Y
      }));
      
      setChps(chpsData);
      setHouses(housesData);
      
      const statuses = {};
      chpsData.forEach(chp => {
        statuses[chp.id] = checkChpStatus(chp.id, housesData);
      });
      setChpStatus(statuses);
      
      const parsedId = parseInt(id);
      const foundChp = chpsData.find(c => c.id === parsedId);
      if (foundChp) {
        setEntity(foundChp);
        setEntityType('chp');
      } else {
        const foundHouse = housesData.find(h => h.id === parsedId);
        if (foundHouse) {
          setEntity(foundHouse);
          setEntityType('house');
        }
      }
    } catch (err) {
      setNotification({ message: 'Ошибка загрузки данных', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [id, api, checkChpStatus]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const updateTemperature = async (newTemp) => {
    if (entityType !== 'house') return;
    
    let finalTemp = newTemp;
    if (finalTemp < 40) finalTemp = 40;
    if (finalTemp > 95) finalTemp = 95;
    
    const updated = { ...entity, temperature: finalTemp };
    
    try {
      await api.put(`/houses/${entity.id}`, {
        Температура: finalTemp
      });
      
      setEntity(updated);
      const updatedHouses = houses.map(h => h.id === entity.id ? updated : h);
      const statuses = {};
      chps.forEach(chp => {
        statuses[chp.id] = checkChpStatus(chp.id, updatedHouses);
      });
      setChpStatus(statuses);
      setHouses(updatedHouses);
      
      if (finalTemp !== newTemp) {
        showNotification(`Температура ограничена ${finalTemp}°C (допустимый диапазон 40-95°C)`);
      } else {
        showNotification(`Температура изменена на ${finalTemp}°C`);
      }
    } catch (err) {
      showNotification('Ошибка при изменении температуры', 'error');
    }
  };


  const getTemperatureStatus = (temp) => {
    if (temp < 40 || temp > 95) return 'broken';
    if (temp < 60) return 'cold';
    if (temp <= 80) return 'normal';
    return 'hot';
  };

  const getTemperatureColor = (temp) => {
    const status = getTemperatureStatus(temp);
    switch(status) {
      case 'broken': return '#000000';
      case 'cold': return '#4299e1';
      case 'normal': return '#ed8936';
      case 'hot': return '#e53e3e';
      default: return '#718096';
    }
  };

  const getPipeColor = (temp, isChpOff = false) => {
    if (isChpOff) return '#000000';
    const status = getTemperatureStatus(temp);
    switch(status) {
      case 'broken': return '#000000';
      case 'cold': return '#4299e1';
      case 'normal': return '#ed8936';
      case 'hot': return '#e53e3e';
      default: return '#718096';
    }
  };

  const getTemperatureLabel = (temp) => {
    const status = getTemperatureStatus(temp);
    switch(status) {
      case 'broken': return 'ПОЛОМКА - ТРЕБУЕТСЯ РЕМОНТ';
      case 'cold': return 'Низкая нагрузка (холодная вода)';
      case 'normal': return 'Нормальная нагрузка';
      case 'hot': return 'Высокая нагрузка (горячая вода)';
      default: return 'Неизвестно';
    }
  };

  const getTemperatureIcon = (temp) => {
    const status = getTemperatureStatus(temp);
    switch(status) {
      case 'broken': return '💀';
      case 'cold': return '❄️';
      case 'normal': return '🔥';
      case 'hot': return '🌋';
      default: return '❓';
    }
  };

  const deleteEntity = async () => {
    const entityName = entity.name;
    let confirmMessage;
    
    if (entityType === 'chp') {
      const relatedHousesCount = houses.filter(h => h.chpId === entity.id).length;
      if (relatedHousesCount > 0) {
        confirmMessage = `Вы уверены, что хотите удалить ТЭЦ "${entityName}"?\n\nВНИМАНИЕ: Все ${relatedHousesCount} домов, подключённых к этой ТЭЦ, также будут удалены!\nЭто действие нельзя отменить.`;
      } else {
        confirmMessage = `Вы уверены, что хотите удалить ТЭЦ "${entityName}"?\n\nЭто действие нельзя отменить.`;
      }
    } else {
      confirmMessage = `Вы уверены, что хотите удалить дом "${entityName}"?\n\nЭто действие нельзя отменить.`;
    }
    
    if (!window.confirm(confirmMessage)) return;
    
    try {
      if (entityType === 'chp') {
        await api.delete(`/chps/${entity.id}`);
      } else {
        await api.delete(`/houses/${entity.id}`);
      }
      showNotification(`${entityName} успешно удалён`);
      navigate('/');
    } catch (err) {
      showNotification('Ошибка при удалении', 'error');
    }
  };

  if (loading) return <div className="loading">Загрузка...</div>;
  if (!entity) return <div className="error">Объект не найден</div>;

  const relatedHouses = entityType === 'chp' ? houses.filter(h => h.chpId === entity.id) : [];
  const isChpOff = entityType === 'house' ? chpStatus[entity.chpId] === 'off' : chpStatus[entity.id] === 'off';

  return (
    <div className="page">
      {notification && (
        <div className={`notification notification-${notification.type}`}>
          {notification.message}
        </div>
      )}
      <button className="btn btn-primary" onClick={() => navigate(-1)} style={{ marginBottom: '1rem' }}>
        ← Назад
      </button>
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            {entityType === 'chp' ? 'ТЭЦ' : (entity.type === 'apartment' ? 'Многоквартирный' : 'Частный')} {entity.name}
            {isChpOff && <span style={{ color: '#f56565', marginLeft: '10px', fontSize: '0.9rem' }}>(ОТКЛЮЧЕНА)</span>}
          </div>
          <div>
            <button className="btn btn-danger" onClick={deleteEntity}>Удалить</button>
          </div>
        </div>
        {entityType === 'chp' ? (
          <>
            <p><strong>Мощность:</strong> {entity.capacity} МВт</p>
            <p><strong>Расположение:</strong> {entity.location}</p>
            <p><strong>Количество домов:</strong> {relatedHouses.length}</p>
            <p><strong>Статус:</strong> <span style={{ color: chpStatus[entity.id] === 'off' ? '#f56565' : '#48bb78', fontWeight: 'bold' }}>
              {chpStatus[entity.id] === 'off' ? 'Отключена' : 'Работает'}
            </span></p>
            <h3 style={{ marginTop: '2rem' }}>Подключённые дома:</h3>
            {relatedHouses.length === 0 ? (
              <p>Нет подключённых домов</p>
            ) : (
              <div className="grid">
                {relatedHouses.map(house => {
                  const isHouseChpOff = chpStatus[entity.id] === 'off';
                  return (
                    <div key={house.id} className="card" onClick={() => navigate(`/detail/${house.id}`)}>
                      <div className="card-header">
                        <div className="card-title">
                          {house.type === 'apartment' ? 'Многоквартирный' : 'Частный'} {house.name}
                        </div>
                      </div>
                      <p><strong>Температура:</strong> {house.temperature}°C</p>
                      <div style={{
                        height: '10px',
                        background: getPipeColor(house.temperature, isHouseChpOff),
                        borderRadius: '5px',
                        marginTop: '10px'
                      }}></div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <>
            <p><strong>Тип:</strong> {entity.type === 'apartment' ? 'Многоквартирный дом' : 'Частный дом'}</p>
            <p><strong>ТЭЦ:</strong> 
              <span style={{ color: chpStatus[entity.chpId] === 'off' ? '#f56565' : 'inherit' }}>
                {chps.find(c => c.id === entity.chpId)?.name || 'Не указана'}
                {chpStatus[entity.chpId] === 'off' && ' (ОТКЛЮЧЕНА)'}
              </span>
            </p>
            
            <div style={{ margin: '1rem 0', padding: '1rem', background: '#f7fafc', borderRadius: '10px' }}>
              <p><strong>Температура воды в трубе:</strong></p>
              <div style={{
                display: 'inline-block',
                padding: '0.5rem 1.5rem',
                borderRadius: '25px',
                background: isChpOff ? '#000000' : getTemperatureColor(entity.temperature),
                color: 'white',
                fontSize: '1.5rem',
                fontWeight: 'bold',
                marginBottom: '1rem'
              }}>
                {getTemperatureIcon(entity.temperature)} {entity.temperature}°C
              </div>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <button className="btn btn-warning" onClick={() => updateTemperature(entity.temperature - 5)}>
                  -5°C
                </button>
                <button className="btn btn-warning" onClick={() => updateTemperature(entity.temperature - 1)}>
                  -1°C
                </button>
                <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{entity.temperature}°C</span>
                <button className="btn btn-warning" onClick={() => updateTemperature(entity.temperature + 1)}>
                  +1°C
                </button>
                <button className="btn btn-warning" onClick={() => updateTemperature(entity.temperature + 5)}>
                  +5°C
                </button>
              </div>
              <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#718096' }}>
                Допустимый диапазон: 40°C - 95°C
              </div>
            </div>
            <div style={{ marginTop: '1rem', padding: '1rem', background: '#e2e8f0', borderRadius: '10px' }}>
              <p><strong>Влияние на систему отопления:</strong></p>
              <div style={{
                height: '20px',
                background: '#cbd5e0',
                borderRadius: '10px',
                overflow: 'hidden',
                marginTop: '0.5rem'
              }}>
                <div style={{
                  width: `${((entity.temperature - 40) / 55) * 100}%`,
                  height: '100%',
                  background: isChpOff ? '#000000' : getPipeColor(entity.temperature),
                  transition: 'width 0.3s'
                }}></div>
              </div>
              <p style={{ marginTop: '0.5rem' }}>
                <strong>Нагрузка:</strong> 
                <span style={{ color: isChpOff ? '#000000' : getTemperatureColor(entity.temperature), fontWeight: 'bold', marginLeft: '0.5rem' }}>
                  {isChpOff ? 'ТЭЦ ОТКЛЮЧЕНА' : getTemperatureLabel(entity.temperature)}
                </span>
              </p>
              <p><strong>Цвет трубы:</strong> 
                <span style={{
                  display: 'inline-block',
                  width: '20px',
                  height: '20px',
                  background: isChpOff ? '#000000' : getPipeColor(entity.temperature),
                  borderRadius: '3px',
                  marginLeft: '0.5rem',
                  verticalAlign: 'middle'
                }}></span>
              </p>
              {isChpOff && (
                <p style={{ color: '#f56565', fontWeight: 'bold', marginTop: '0.5rem' }}>
                  ТЭЦ ОТКЛЮЧЕНА! Все дома имеют одинаковую экстремальную температуру!
                </p>
              )}
              {!isChpOff && getTemperatureStatus(entity.temperature) === 'broken' && (
                <p style={{ color: '#000000', fontWeight: 'bold', marginTop: '0.5rem' }}>
                  ТРЕБУЕТСЯ СРОЧНЫЙ РЕМОНТ! Температура вне допустимого диапазона!
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default Detail;